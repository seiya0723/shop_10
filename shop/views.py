from django.shortcuts import render,redirect


from django.contrib.auth.mixins import LoginRequiredMixin

#from django.views import View
from rest_framework.views import APIView as View

from django.http.response import JsonResponse
from django.template.loader import render_to_string

from .models import Product,Cart
from .forms import CartForm,ProductSortForm



import stripe
from django.urls import reverse_lazy
from django.conf import settings


class IndexView(View):

    def get(self, request, *args, **kwargs):

        context             = {}

        #並び替え用のフォーム
        context["choices"]  = [ { "value":choice[0], "label":choice[1] }  for choice in ProductSortForm.choices ]

        form    = ProductSortForm(request.GET)

        #並び替えが指定されている場合。(後に検索をするのであれば、変数order_byに並び替えする値を格納)
        if form.is_valid():
            cleaned             = form.clean()
            context["products"] = Product.objects.order_by(cleaned["order_by"])
        else:
            context["products"] = Product.objects.all()


        #TODO:ここで検索をする。(価格帯、商品カテゴリ、)


        #これは簡潔に修正したほうが良いだろう。都道府県を指定する方法を使えばどうにかなると思われる。
        """
        #並び替えが指定されている。
        if "order_by" in request.GET:
            #その並び替えが指定のリストの中にある。
            if request.GET["order_by"] in keys:
                context["products"] = Product.objects.order_by(request.GET["order_by"])

            else:
                context["products"] = Product.objects.all()
        else:
            context["products"] = Product.objects.all()
        """

        return render(request, "shop/index.html", context)

index   = IndexView.as_view()


class ProductView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):
        #TODO:ここに商品の個別ページを作る

        product = Product.objects.filter(id=pk).first()

        if not product:
            return redirect("shop:index")

        context = {}
        context["product"]  = product

        return render(request, "shop/product.html", context)


    def post(self, request, pk, *args, **kwargs):
        #ここでユーザーのカートへ追加
        if request.user.is_authenticated:

            copied  = request.POST.copy()

            copied["user"]      = request.user.id
            copied["product"]   = pk

            form    = CartForm(copied)

            if not form.is_valid():
                print("バリデーションNG")
                return redirect("shop:index")


            print("バリデーションOK")

            #TIPS:ここで既に同じ商品がカートに入っている場合、レコード新規作成ではなく、既存レコードにamount分だけ追加する。
            cart    = Cart.objects.filter(user=request.user.id, product=pk).first()

            if cart:
                cleaned = form.clean()

                #TODO:ここでカートに数量を追加する時、追加される数量が在庫数を上回っていないかチェックする。上回る場合は拒否する。
                if cart.amount_change(cart.amount + cleaned["amount"]):
                    cart.amount += cleaned["amount"]
                    cart.save()
                else:
                    print("在庫数を超過しているため、カートに追加できません。")

            else:          
                #存在しない場合は新規作成
                form.save()

        else:
            print("未認証です")
            #TODO:未認証ユーザーにはCookieにカートのデータを格納するのも良い

        return redirect("shop:index")

product = ProductView.as_view()



#pkは、GETとPOSTの場合は商品ID、PUTとDELETEの場合はレビューID
class ProductCommentView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューをページネーションで閲覧できるようにする。
        pass

    def post(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューをDBに格納。
        pass

    def put(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューを編集する
        pass

    def delete(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューを削除する
        pass

product_comment = ProductCommentView.as_view()


class CartView(LoginRequiredMixin,View):

    def get_context(self, request):
        #ここでカートの中身を表示
        context = {}
        carts   = Cart.objects.filter(user=request.user.id)

        context["total"]    = 0
        for cart in carts:
            context["total"] += cart.total()

        context["carts"]    = carts
        
        return context


    def get(self, request, *args, **kwargs):
        context = self.get_context(request)

        return render(request, "shop/cart.html", context)


    def put(self, request, *args, **kwargs):
        #ここでカートの数量変更を受け付ける。
        
        data    = { "error":True }
        
        if "pk" not in kwargs:
            return JsonResponse(data)
        
        #リクエストがあったカートモデルのidとリクエストしてきたユーザーのidで検索する
        #(ユーザーで絞り込まない場合。第三者のカート内数量を勝手に変更されるため。)
        cart    = Cart.objects.filter(id=kwargs["pk"],user=request.user.id).first()

        if not cart:
            return JsonResponse(data)

        copied          = request.data.copy()
        copied["user"]  = request.user.id
        

        #編集対象を特定して数量を変更させる。
        form    = CartForm(copied,instance=cart)

        if not form.is_valid():
            print("バリデーションNG")
            print(form.errors)
            return JsonResponse(data)


        print("バリデーションOK")

        cleaned = form.clean()

        if not cart.amount_change(cleaned["amount"]):
            print("数量が在庫数を超過。")
            return JsonResponse(data)

        #数量が規定値であれば編集
        form.save()

        context         = self.get_context(request)
        data["content"] = render_to_string("shop/cart_content.html", context, request)
        data["error"]   = False

        return JsonResponse(data)

    def delete(self, request, *args, **kwargs):
        data    = {"error":True}

        if "pk" not in kwargs:
            return JsonResponse(data)

        cart    = Cart.objects.filter(id=kwargs["pk"],user=request.user.id).first()

        if not cart:
            return JsonResponse(data)

        cart.delete()

        context         = self.get_context(request)
        data["content"] = render_to_string("shop/cart_content.html", context, request)
        data["error"]   = False

        return JsonResponse(data)

cart = CartView.as_view()


#決済ページ
class CheckoutView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        context = {}

        #セッションを開始するため、秘密鍵をセットする。
        stripe.api_key = settings.STRIPE_API_KEY

        #カート内の商品情報を取得、Stripeのセッション作成に使う。
        carts   = Cart.objects.filter(user=request.user.id)

        items   = []
        for cart in carts:
            items.append( {'price_data': { 'currency': 'jpy', 'product_data': { 'name': cart.product.name }, 'unit_amount': cart.product.price }, 'quantity': cart.amount } ) 

        session = stripe.checkout.Session.create(
                payment_method_types=['card'],

                #顧客が購入する商品
                line_items=items,

                mode='payment',

                #決済成功した後のリダイレクト先
                success_url=request.build_absolute_uri(reverse_lazy("shop:checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",

                #決済キャンセルしたときのリダイレクト先
                cancel_url=request.build_absolute_uri(reverse_lazy("shop:checkout_error")),
                )


        print(session)

        #この公開鍵を使ってテンプレート上のJavaScriptにセットする。顧客が入力する情報を暗号化させるための物
        context["public_key"]   = settings.STRIPE_PUBLISHABLE_KEY

        #このStripeのセッションIDをテンプレート上のJavaScriptにセットする。上記のビューで作ったセッションを顧客に渡して決済させるための物
        context["session_id"]   = session["id"]


        return render(request, "shop/checkout.html", context)

checkout    = CheckoutView.as_view()

#決済成功ページ
class CheckoutSuccessView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        #セッションIDがパラメータに存在するかチェック。なければエラー画面へ
        if "session_id" not in request.GET:
            return redirect("shop:checkout_error")

        #ここでセッションの存在チェック(存在しないセッションIDを適当に入力した場合、ここでエラーが出る。)
        #1度でもここを通ると、exceptになる。(決済成功した後更新ボタンを押すと、例外が発生。)
        try:
            session     = stripe.checkout.Session.retrieve(request.GET["session_id"])
            print(session)
        except Exception as e:
            print(e)
            return redirect("shop:checkout_error")

        context = {}

        #TODO:ここで現在指定している住所、カートの中身を元にOrderモデルへ記録を行う。

        return render(request, "shop/checkout_success.html", context)

checkout_success    = CheckoutSuccessView.as_view()

#決済失敗ページ
class CheckoutErrorView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        context = {}

        return render(request, "shop/checkout_error.html", context)


checkout_error    = CheckoutErrorView.as_view()



