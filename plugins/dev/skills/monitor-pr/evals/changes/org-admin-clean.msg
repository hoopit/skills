BAC-4412: One org-admin check for the bank account list

The list view asked "is this user an org admin?" twice: inline in
get_queryset, and in _can_view_balance for the balance column and the
export. Both now call _is_org_admin, so the two can't drift apart.
No behaviour change.
