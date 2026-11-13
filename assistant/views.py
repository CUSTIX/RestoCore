from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from assistant import services
from assistant.forms import AskForm
from assistant.llm import AssistantUnavailable
from core.mixins import RoleRequiredMixin
from core.roles import OWNER


def _turn(turn: dict) -> dict:
    return {**turn, "blocks": services.format_answer(turn["a"])}


class AssistantView(RoleRequiredMixin, TemplateView):
    """Owner-only chat. Works without JavaScript (form post + redirect); the page script posts
    with fetch and gets JSON back so the conversation updates in place."""

    allowed_roles = (OWNER,)
    template_name = "assistant/chat.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "active_section": "assistant",
            "form": kwargs.get("form") or AskForm(),
            "turns": [_turn(t) for t in services.history(self.request.session)],
            "enabled": services.is_enabled(),
            "suggestions": services.SUGGESTIONS,
            "limit_message": services.limit_message(self.request.user),
        }

    def post(self, request, *args, **kwargs):
        wants_json = request.headers.get("X-Requested-With") == "fetch"
        if request.POST.get("action") == "clear":
            services.clear_history(request.session)
            return JsonResponse({"cleared": True}) if wants_json else redirect("assistant:chat")
        form = AskForm(request.POST)
        if not form.is_valid():
            error = form.errors["question"][0]
            if wants_json:
                return JsonResponse({"error": error}, status=400)
            return self.render_to_response(self.get_context_data(form=form))
        try:
            answer = services.ask(
                form.cleaned_data["question"], user=request.user, session=request.session
            )
        except AssistantUnavailable as exc:
            if wants_json:
                return JsonResponse({"error": str(exc)}, status=503)
            messages.error(request, str(exc))
            return redirect("assistant:chat")
        if wants_json:
            return JsonResponse(
                {"blocks": services.format_answer(answer.text), "sources": answer.sources}
            )
        return redirect("assistant:chat")
