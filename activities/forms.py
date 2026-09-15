from django import forms

from .models import ActivityType


class ConversationForm(forms.Form):
    activity_type = forms.ChoiceField(
        choices=[
            (ActivityType.CALL, "Call"),
            (ActivityType.EMAIL, "Email"),
            (ActivityType.MEETING, "Meeting"),
        ]
    )
    occurred_at = forms.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M"],
        widget=forms.DateTimeInput(
            format="%d/%m/%Y %H:%M", attrs={"placeholder": "DD/MM/YYYY HH:mm"}
        ),
    )
    details = forms.CharField(widget=forms.Textarea)
    follow_up_on = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(format="%d/%m/%Y", attrs={"placeholder": "DD/MM/YYYY"}),
    )
    follow_up_summary = forms.CharField(required=False, widget=forms.Textarea)

    def clean(self):
        cleaned_data = super().clean()
        due_on = cleaned_data.get("follow_up_on")
        summary = cleaned_data.get("follow_up_summary")
        if bool(due_on) != bool(summary):
            raise forms.ValidationError("A follow-up needs both a due date and summary.")
        return cleaned_data


class FollowUpForm(forms.Form):
    due_on = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(format="%d/%m/%Y", attrs={"placeholder": "DD/MM/YYYY"}),
    )
    summary = forms.CharField(widget=forms.Textarea)
