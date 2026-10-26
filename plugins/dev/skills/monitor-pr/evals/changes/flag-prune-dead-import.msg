GH-90880: Drop the dead TYPE_CHECKING block from the flag prune task

featureflags/tasks.py imported TYPE_CHECKING only for an empty
`if TYPE_CHECKING: pass`. No behaviour change.
