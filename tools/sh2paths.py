"""Central path config for all SH2 tools.

Environment variables (all optional):
  SH2_GAME_DIR  root of the game install (the folder containing
                'SOUL HACKERS2_Data'). Default below.
  SH2_DEC       folder holding files decrypted by decrypt_all.py
                (mirrors the win/ tree). Default: ../dec
  SH2_OLD       optional legacy working directory that contains extra
                capture files (_commontable.dec, gimmicks.json,
                event_points.json, _msg_common_*.json). Not required if
                msg_dump.py has been run and files exist in tools/data.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('SH2_OUT') or os.path.join(HERE, '..', 'out')
DATA = os.path.join(HERE, 'data')

GAME = os.environ.get('SH2_GAME_DIR') or r'C:/Games/Soul Hackers 2'
SS = GAME + '/SOUL HACKERS2_Data/StreamingAssets'
WIN = SS + '/win'
DEC = os.environ.get('SH2_DEC') or os.path.join(HERE, '..', 'dec')
OLD = os.environ.get('SH2_OLD') or ''


def oldfile(name):
    """Optional capture file: legacy dir first, then bundled tools/data."""
    for d in (OLD, DATA):
        p = os.path.join(d or '\0', name)
        if d and os.path.exists(p):
            return p
    return os.path.join(OLD or DATA, name)


COMBOS = oldfile('dbg_all_combos.txt')


def commontable_dec():
    p = os.path.join(DEC, 'win', 'Table', 'commontable')
    if os.path.exists(p):
        return p
    return oldfile('_commontable.dec')


def msg_common(lang):
    """label->text json produced by msg_dump.py (or the legacy dumps)."""
    for p in (os.path.join(OUT, f'msg_common_{lang}.json'),
              os.path.join(OLD or '\0', f'_msg_common_{lang}.json')):
        if os.path.exists(p):
            return p
    return None


def dec(path_under_win):
    """Path to a decrypted file, e.g. dec('Message/En/common')."""
    return os.path.join(DEC, 'win', *path_under_win.split('/'))
