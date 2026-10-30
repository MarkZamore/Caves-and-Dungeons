"""Forge47.4 KeyMapping.same model, independently checked against native pairs.

This is the native Controls-screen comparator, not proof that two author
activation predicates can run together. Intentional exceptions need exact names.
"""
MODIFIER_KEYS = {
    'SHIFT': {'key.keyboard.left.shift', 'key.keyboard.right.shift'},
    'CONTROL': {'key.keyboard.left.control', 'key.keyboard.right.control'},
    'ALT': {'key.keyboard.left.alt', 'key.keyboard.right.alt'},
    'NONE': set(),
}

def context_conflicts(first, second):
    return first == 'UNIVERSAL' or first == second

def modifier_matches(modifier, key):
    return key in MODIFIER_KEYS[modifier]

def constructor_normalize(modifier, key):
    return 'NONE' if modifier_matches(modifier, key) else modifier

def native_same(first, second):
    """(context, modifier, serialized physical key) -> exact native result."""
    ac, am, ak = first
    bc, bm, bk = second
    if context_conflicts(ac, bc) or context_conflicts(bc, ac):
        if modifier_matches(am, bk) or modifier_matches(bm, ak):
            return True
        if ak == bk:
            return am == bm or (context_conflicts(ac, 'IN_GAME') and (am == 'NONE' or bm == 'NONE'))
    return ak == bk
