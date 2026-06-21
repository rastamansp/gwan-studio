from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class StudioUserCreationForm(UserCreationForm):
    username = forms.CharField(
        label='Usuario',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'input',
                'autocomplete': 'username',
                'autofocus': True,
                'placeholder': 'Seu usuario',
            }
        ),
        help_text='Use letras, numeros e @/./+/-/_ para criar seu acesso.',
    )
    password1 = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'input',
                'autocomplete': 'new-password',
                'placeholder': 'Sua senha',
            }
        ),
        help_text='Crie uma senha forte com pelo menos 8 caracteres.',
    )
    password2 = forms.CharField(
        label='Confirmar senha',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'input',
                'autocomplete': 'new-password',
                'placeholder': 'Repita a senha',
            }
        ),
        help_text='Repita a senha para confirmar o cadastro.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)
