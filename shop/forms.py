from django import forms 

from .models import Cart

class CartForm(forms.ModelForm):

    class Meta:
        model   = Cart
        fields  = [ "user","product","amount" ]

class ProductSortForm(forms.Form):

    #並び替えの選択肢を作る
    choices         = [
                        ("price","価格安い順"),
                        ("-price","価格高い順"),
                    ]

    #並び替えバリデーション用のフィールド
    order_by        = forms.ChoiceField(choices=choices)

