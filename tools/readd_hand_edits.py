#!/usr/bin/env python3
"""Re-apply RecompiledFuncs hand-edits after a regen (Virtual Pro Wrestling 64).

Every N64Recomp regen wipes edits made directly in RecompiledFuncs/*.c; register them
here (idempotent, safe to re-run) and run this AFTER the regen pipeline. Anchors are exact
generated lines; a missing anchor fails loudly (regen output changed shape).
"""

# [vpw64][rt] Ray tracing experiment (exp/raytracing; src/game/raytracing.cpp): hand RT64
# the real camera. RT64 only uses it while ray tracing is active (menu option or WCW_RT).
def rt_hand_edits():
    import os as _os
    funcs = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'RecompiledFuncs')
    def _load(fn):
        with open(_os.path.join(funcs, fn), 'rb') as f:
            return f.read().decode('utf-8', errors='replace').splitlines(keepends=True)
    def _save(fn, lines):
        with open(_os.path.join(funcs, fn), 'wb') as f:
            f.write(''.join(lines).encode('utf-8'))
    def _body(lines, name):
        sig = 'RECOMP_FUNC void %s(' % name
        start = next((i for i, l in enumerate(lines) if l.startswith(sig)), None)
        if start is None:
            return None, None
        end = next((i for i in range(start, len(lines)) if lines[i].rstrip('\r\n') == ';}'), None)
        return start, end
    def _insert_after_all(fn, func, anchor, text, expect):
        lines = _load(fn)
        if any('[vpw64][rt]' in l for l in lines[slice(*_body(lines, func))] if l):
            return '%s already present' % func
        lo, hi = _body(lines, func)
        if lo is None or hi is None:
            raise SystemExit('rt: cannot locate %s in %s' % (func, fn))
        hits = [i for i in range(lo, hi) if lines[i].rstrip('\r\n') == anchor]
        if len(hits) != expect:
            raise SystemExit('rt: anchor %r matched %d times in %s (expected %d)' % (anchor, len(hits), func, expect))
        for i in reversed(hits):
            lines[i + 1:i + 1] = text
        _save(fn, lines)
        return '%s (%d site(s))' % (func, len(hits))
    done = []
    # The latch sits in the matrix multiply func_800016FC calls, not in func_800016FC itself:
    # mods hook func_800016FC (AkiMods' camera) and a hooked function is recompiled from the
    # ROM without hand-edits. Older generated files had it in func_800016FC: strip that site.
    lines = _load('funcs_0.c')
    old = next((i for i, l in enumerate(lines) if '[vpw64][rt] camera latch: a1 = P, a2 = V' in l), None)
    if old is not None:
        del lines[old:old + 3]
        _save('funcs_0.c', lines)
        done.append('removed old latch in func_800016FC')
    done.append(_insert_after_all('funcs_0.c', 'func_8000209C', '    int c1cs = 0;', [
        '    { /* [vpw64][rt] camera latch: a0 = V, a1 = P, a2 = product (the camera matrix when called from the camera builder) */\n',
        '      extern void wcw_rt_latch_camera_multiply(uint8_t* rdram, uint32_t view_vaddr, uint32_t proj_vaddr, uint32_t dest_vaddr);\n',
        '      wcw_rt_latch_camera_multiply(rdram, (uint32_t)ctx->r4, (uint32_t)ctx->r5, (uint32_t)ctx->r6); }\n'], 1))
    done.append(_insert_after_all('funcs_1.c', 'func_80003358', '    func_80002C50(rdram, ctx);', [
        '    { /* [vpw64][rt] after the frame DL head is returned in v0 */\n',
        '      extern uint32_t wcw_rt_emit_camera(uint8_t* rdram, uint32_t gfx);\n',
        '      ctx->r2 = (int64_t)(int32_t)wcw_rt_emit_camera(rdram, (uint32_t)ctx->r2); }\n'], 2))
    return 'rt camera hand-off: ' + '; '.join(done)


# [wcw fix] Widescreen cull (aki-roadmap#47 / #5). func_800025E4 is the per-object view cull (the 1997
# engine's version of No Mercy's func_800024F8, the same as World Tour's func_8000252C): it returns 0
# (culled) when |x| / (depth + 150) > 1.5 or |y| / (depth + 150) > 1.5 (view space). That is about 3.8x
# the 4:3 screen edge, but with Aspect Ratio = Expand RT64 shows a wider view, and large set pieces whose
# center is past the line while their geometry reaches into the extra width were culled at the screen
# edges (edge pop-in). Scale only the horizontal limit by the screen's widening
# (wcw_widescreen_cull_scale, src/game/recomp_api.cpp: 1 at Original). The projection is untouched
# (RT64's Expand widens it). Never hook func_800025E4 from a mod: a hooked function is recompiled from
# the ROM without this edit.
WCW_CULL_FUNC = 'func_800025E4'
WCW_CULL_X_COMPARE = '    c1cs = ctx->f12.d < ctx->f16.d;'
WCW_CULL_Y_COMPARE = '    c1cs = ctx->f12.d < ctx->f4.d;'
WCW_CULL_EDIT = [
    '    /* [wcw fix] widescreen cull: the horizontal limit follows the screen width (aki-roadmap#47). */\n',
    '    c1cs = (ctx->f12.d * wcw_widescreen_cull_scale()) < ctx->f16.d;\n',
]
WCW_CULL_DECLS = [
    '/* [wcw fix] widescreen cull scale, implemented in src/game/recomp_api.cpp. */\n',
    'extern double wcw_widescreen_cull_scale(void);\n',
]

def widescreen_cull_edit():
    """Replace the cull's horizontal compare in place. Fails loudly if the generated code changed shape."""
    import glob, os as _os, sys as _sys
    funcs = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'RecompiledFuncs')
    sig = 'RECOMP_FUNC void %s(' % WCW_CULL_FUNC
    for path in sorted(glob.glob(_os.path.join(funcs, 'funcs_*.c'))):
        with open(path, 'rb') as f:
            lines = f.read().decode('utf-8', errors='replace').splitlines(keepends=True)
        start = next((i for i, l in enumerate(lines) if l.startswith(sig)), None)
        if start is None:
            continue
        if any('wcw_widescreen_cull_scale' in l for l in lines):
            return 'widescreen cull (already present)'
        end = next(i for i in range(start, len(lines)) if lines[i].rstrip('\r\n') == ';}')
        xs = [i for i in range(start, end) if lines[i].rstrip('\r\n') == WCW_CULL_X_COMPARE]
        ys = [i for i in range(start, end) if lines[i].rstrip('\r\n') == WCW_CULL_Y_COMPARE]
        if len(xs) != 1 or len(ys) != 1 or xs[0] > ys[0]:
            _sys.exit('widescreen cull: %s changed shape (%d x compares, %d y compares); re-derive the edit'
                      % (WCW_CULL_FUNC, len(xs), len(ys)))
        lines[xs[0]:xs[0] + 1] = WCW_CULL_EDIT
        last_include = max((i for i, l in enumerate(lines) if l.startswith('#include')), default=-1)
        lines[last_include + 1:last_include + 1] = WCW_CULL_DECLS
        with open(path, 'wb') as f:
            f.write(''.join(lines).encode('utf-8'))
        return 'widescreen cull -> %s %s' % (_os.path.basename(path), WCW_CULL_FUNC)
    _sys.exit('widescreen cull: %s not found in RecompiledFuncs' % WCW_CULL_FUNC)


if __name__ == '__main__':
    print('readd_hand_edits: ' + rt_hand_edits())
    print('readd_hand_edits: ' + widescreen_cull_edit())
