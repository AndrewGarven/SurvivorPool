from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update({
            "placeholder": "Username"
        })
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Password"
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm password"
        })
