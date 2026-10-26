Ask the org-admin question once per request

Reviewer finding (codex · Low):
_is_org_admin runs its query twice per list request, once in
get_queryset and once in get_serializer_context.

Solution:
Cache it per view instance with @cached_method, as the comment views do.
