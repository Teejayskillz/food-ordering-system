from django import forms
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

class ProfileForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = Profile
        fields = ["phone", "default_address"]
        widgets = {
            "default_address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

        if user:
            # Prefill name from user.first_name (we stored full name there earlier)
            self.fields["full_name"].initial = user.first_name

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if self.user is not None:
            self.user.first_name = self.cleaned_data.get("full_name", "").strip()
            if commit:
                self.user.save()
        return profile
