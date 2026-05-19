"""智能股票分析助手 - 后端应用"""

# ==== 必须在所有导入前！monkey-patch print 解决 Windows GBK 编码问题 ====
import builtins as _builtins
_original_print = _builtins.print

def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except UnicodeEncodeError:
        safe_args = []
        for a in args:
            try:
                s = str(a)
            except Exception:
                s = repr(a)
            safe_args.append(s.encode('ascii', errors='replace').decode('ascii'))
        try:
            _original_print(*safe_args, **kwargs)
        except Exception:
            pass  # 彻底放弃

_builtins.print = _safe_print
# ======================================================================

__version__ = "1.0.0"
