# -*- coding: utf-8 -*-
"""중앙데스크 회차 반영기 — 수집한 후보를 P0·94·91에 쌓고 P1 시작값을 전환한다.

  python central_desk_round.py payload.json            # 드라이런(계획만)
  python central_desk_round.py payload.json --apply    # 반영

payload.json 형식 (줄기 하나만 넣어도 되고 셋 다 넣어도 된다):
{
  "round_id": "AM-20260903-01",          # 없으면 오늘 날짜로 자동 생성
  "base_date": "2026-09-03",             # 없으면 오늘
  "signals":  [ {...}, {...}, {...} ],   # 해외 신호  (0 또는 3건)
  "products": [ {...}, {...}, {...} ],   # 제품 후보  (0 또는 3건)
  "contents": [ {...}, {...}, {...} ]    # 콘텐츠 후보 (0 또는 3건)
}

각 항목의 칸 이름은 COLLECTION_PLAYBOOK.md 참조.

설계 메모
  · 세 줄기는 P0에서 서로 다른 열 묶음을 쓰고, P1도 각 열에서 따로 MATCH 한다.
    그래서 줄기마다 주기가 달라도 서로 간섭하지 않는다. 각 줄기는 자기 열의
    마지막 사용 행 다음에 3행을 붙인다(다른 줄기와 행이 어긋나도 정상).
  · 쓰기 전 전체 스냅샷을 남긴다. 실패 시 되돌릴 수 있다.
  · P1은 시작값 3칸의 '값'만 바꾸고 수식·서식은 건드리지 않는다.
  · 새 회차이므로 콘텐츠 선택 체크박스는 FALSE로 초기화한다(사용자가 다시 선택).
  · 자격증명: add9_creds.get_gspread_client() — 로컬 파일 또는 ADD9_SA_JSON 환경변수.
"""
import sys
import json
import datetime
import pathlib
import os

from add9_creds import get_gspread_client

SHEET_ID = '1N28JERpj9Es4eTPUO_nGMYWwvRfeXQTfg72BChQEI6Q'
ADD9 = 'https://docs.google.com/spreadsheets/d/1NqbsDi367m9C9CclTFhovQ9EaRBW80JOz3JoBJD_o6w/edit'
BEAUTY = 'https://docs.google.com/spreadsheets/d/1Q50ERfvqs16YU58gg5zRJ0kdm8N1NN9XvD52HorK6yE/edit'
P0_MAX = 100          # P0_시안원본 행 수

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def S(x):
    return '' if x is None else str(x)


def oneline(t):
    return ' / '.join(x.strip() for x in S(t).splitlines() if x.strip())


def last_used_row(vals, col_idx, start=1):
    """vals(0-based 2차원)에서 col_idx 열의 마지막 비어있지 않은 행 번호(1-based)."""
    last = start
    for i, row in enumerate(vals):
        if col_idx < len(row) and S(row[col_idx]).strip():
            last = i + 1
    return last


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('사용법: python central_desk_round.py payload.json [--apply]')
        sys.exit(2)
    dry = '--apply' not in sys.argv
    payload = json.loads(pathlib.Path(args[0]).read_text(encoding='utf-8'))

    today = datetime.date.today()
    base = payload.get('base_date') or today.isoformat()
    rid = payload.get('round_id') or f'AM-{base.replace("-", "")}-01'
    sig = payload.get('signals') or []
    prd = payload.get('products') or []
    con = payload.get('contents') or []

    for name, arr in (('signals', sig), ('products', prd), ('contents', con)):
        if arr and len(arr) != 3:
            print(f'중단: {name}는 0건 또는 정확히 3건이어야 합니다 (현재 {len(arr)}건)')
            sys.exit(1)
    if not (sig or prd or con):
        print('중단: 반영할 항목이 없습니다')
        sys.exit(1)

    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    w_p0, w_94 = sh.worksheet('P0_시안원본'), sh.worksheet('94_해외신호상세')
    w_91, w_p1 = sh.worksheet('91_신문원본'), sh.worksheet('P1_시장뷰_시안')

    # 중복 방지 — 같은 회차·같은 줄기가 이미 들어가 있으면 중단한다.
    # 두 곳(로컬·클라우드)에 스케줄이 다 켜졌거나 같은 날 두 번 돌린 경우를 막는다.
    dup = []
    if sig:
        n94 = [S(r[13]) for r in w_94.get(value_render_option='FORMATTED_VALUE') if len(r) > 13]
        if rid in n94:
            dup.append('해외 신호')
    a91 = [(S(r[0]), S(r[2])) for r in w_91.get(value_render_option='FORMATTED_VALUE') if r]
    if prd and (rid, '제품') in a91:
        dup.append('제품 후보')
    if con and (rid, '콘텐츠') in a91:
        dup.append('콘텐츠 후보')
    if dup and '--force' not in sys.argv:
        print(f'중단: 회차 {rid}에 이미 반영된 줄기가 있습니다 — {", ".join(dup)}')
        print('  다른 스케줄(로컬/클라우드)이 켜져 있는지 확인하세요. 의도한 재실행이면 --force 를 붙입니다.')
        sys.exit(1)

    p0v = w_p0.get(value_render_option='FORMULA')
    sig_row = last_used_row(p0v, 0) + 1     # A열
    prd_row = last_used_row(p0v, 7) + 1     # H열
    con_row = last_used_row(p0v, 17) + 1    # R열
    row94 = last_used_row(w_94.get(value_render_option='FORMULA'), 0) + 1
    row91 = last_used_row(w_91.get(value_render_option='FORMULA'), 0) + 1

    print(f'회차 {rid} ({base})')
    if sig:
        print(f'  해외 신호 3건 → P0 {sig_row}~{sig_row+2}행, 94 {row94}~{row94+2}행')
    if prd:
        print(f'  제품 후보 3건 → P0 {prd_row}~{prd_row+2}행')
    if con:
        print(f'  콘텐츠 후보 3건 → P0 {con_row}~{con_row+2}행')
    n91 = len(prd) + len(con)
    if n91:
        print(f'  아카이브 → 91 {row91}~{row91+n91-1}행')
    for arr, label in ((sig, '신호'), (prd, '제품'), (con, '콘텐츠')):
        for it in arr:
            print(f'    [{label}] {it.get("title") or it.get("display_name")}')

    over = max(sig_row + 2 if sig else 0, prd_row + 2 if prd else 0, con_row + 2 if con else 0)
    if over > P0_MAX:
        print(f'\n중단: P0가 {P0_MAX}행을 넘습니다({over}). 오래된 회차를 정리한 뒤 다시 실행하세요.')
        sys.exit(1)
    if over > P0_MAX - 12:
        print(f'\n경고: P0 잔여 공간이 얼마 없습니다(다음 사용 행 {over}/{P0_MAX}). 정리를 권합니다.')

    if dry:
        print('\n드라이런. --apply 로 반영')
        return

    # 스냅샷
    snapdir = pathlib.Path(os.environ.get('TEMP') or os.environ.get('TMPDIR') or '.') / 'add9_central_snapshots'
    snapdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    snap = {ws.title: ws.get(value_render_option='FORMULA') for ws in sh.worksheets()}
    snapf = snapdir / f'central_{stamp}.json'
    snapf.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    print(f'\n스냅샷: {snapf}')

    # P0 — 해외 신호 (A~E)
    if sig:
        # 알아두면(배경 상식)이 있으면 무슨 일 앞에 붙인다 — 플레이북 §3 문체 규칙 1.
        # 없으면 기존과 완전히 동일한 본문이 만들어진다(하위호환).
        def sig_body(s):
            bg = S(s.get('background', '')).strip()
            head = f"알아두면\n{bg}\n\n" if bg else ''
            return f"{head}무슨 일\n{s['facts']}\n\n왜 중요한가\n{s['conclusion']}"

        block = [[s['title'],
                  sig_body(s),
                  s.get('channels', '블로그·Instagram·Threads'),
                  s.get('verify_state', '').split(' / ')[0],
                  str(sig_row + i)] for i, s in enumerate(sig)]
        w_p0.update(range_name=f'A{sig_row}:E{sig_row+2}', values=block,
                    value_input_option='USER_ENTERED')
        w_p0.update(range_name=f'X{sig_row}:X{sig_row+2}',
                    values=[[s['title']] for s in sig], value_input_option='USER_ENTERED')
        print(f'P0 A/X {sig_row}~{sig_row+2} 반영')

    # P0 — 제품 (H~Q, W)
    if prd:
        block = [[p['display_name'], p['name_ko'], p['one_line'], p['why'], p['strengths'],
                  p['market_signal'], p['tag'], p['url'], str(prd_row + i), p['caution']]
                 for i, p in enumerate(prd)]
        w_p0.update(range_name=f'H{prd_row}:Q{prd_row+2}', values=block,
                    value_input_option='USER_ENTERED')
        w_p0.update(range_name=f'W{prd_row}:W{prd_row+2}',
                    values=[[p.get('spec_basis', '')] for p in prd], value_input_option='USER_ENTERED')
        w_p0.update(range_name=f'Y{prd_row}:Y{prd_row+2}',
                    values=[[p['display_name']] for p in prd], value_input_option='USER_ENTERED')
        print(f'P0 H/W/Y {prd_row}~{prd_row+2} 반영')

    # P0 — 콘텐츠 (R~V)
    if con:
        block = [[c['title'], c['summary'], c['type'], '선택 후 조사', str(con_row + i)]
                 for i, c in enumerate(con)]
        w_p0.update(range_name=f'R{con_row}:V{con_row+2}', values=block,
                    value_input_option='USER_ENTERED')
        w_p0.update(range_name=f'Z{con_row}:Z{con_row+2}',
                    values=[[c['title']] for c in con], value_input_option='USER_ENTERED')
        print(f'P0 R/Z {con_row}~{con_row+2} 반영')

    # 94 — 신호 상세
    if sig:
        rows = [[s['signal_id'], s['published'], s['title'], s['conclusion'], s['facts'],
                 s['for_md'], s['for_ceo'], s['add9_apply'], s['risks'], s['next_track'],
                 s['verify_state'],
                 f'=HYPERLINK("{s["url"]}","{s["anchor"]}")',
                 '평소 미읽기 / 이 신호 선택 시 C:L 한 행만 읽기', rid, 'Claude Code'] for s in sig]
        w_94.update(range_name=f'A{row94}:O{row94+2}', values=rows, value_input_option='USER_ENTERED')
        print(f'94 {row94}~{row94+2} 반영')
        # P열 알아두면 — 94 그리드가 16열 미만이면 조용히 건너뛴다(본 반영을 깨지 않기 위해).
        bgs = [[S(s.get('background', '')).strip()] for s in sig]
        if any(b[0] for b in bgs):
            try:
                w_94.update(range_name=f'P{row94}:P{row94+2}', values=bgs,
                            value_input_option='USER_ENTERED')
                print(f'94 P{row94}~{row94+2} 알아두면 반영')
            except Exception as e:
                print(f'  경고: 94 P열(알아두면) 반영 실패 — {e}. 그리드 16열 확장 필요')

    # 91 — 아카이브
    arch = []
    for n, p in enumerate(prd, 1):
        brand, _, nm = p['display_name'].partition(' · ')
        arch.append([rid, base, '제품', str(n), '', brand, nm or p['display_name'],
                     oneline(p['one_line']), p['why'], p['strengths'], p['market_signal'],
                     p['caution'], p['tag'], p['url'], '', ADD9, 'Claude Code', '후보'])
    for n, c in enumerate(con, 1):
        arch.append([rid, base, '콘텐츠', str(n), '', '', c['title'], oneline(c['summary']),
                     '', '', '', '', c['type'], '', '', BEAUTY, 'Claude Code', '후보'])
    if arch:
        w_91.update(range_name=f'A{row91}:R{row91+len(arch)-1}', values=arch,
                    value_input_option='USER_ENTERED')
        print(f'91 {row91}~{row91+len(arch)-1} 반영')

    # P1 시작값 (값만) + 콘텐츠 체크박스 초기화
    upd = []
    if sig:
        upd.append({'range': 'B5', 'values': [[sig[0]['title']]]})
    if prd:
        upd.append({'range': 'B17', 'values': [[prd[0]['display_name']]]})
    if con:
        upd.append({'range': 'B47', 'values': [[con[0]['title']]]})
        upd += [{'range': a, 'values': [[False]]} for a in ('C50', 'C53', 'C56')]
    w_p1.batch_update(upd, value_input_option='USER_ENTERED')
    print(f'P1 시작값 전환 ({len(upd)}칸)')

    # 검증
    errs = ('#REF!', '#ERROR!', '#VALUE!', '#N/A', '#NAME?', '#DIV/0!')
    bad = 0
    for ws in sh.worksheets():
        for row in ws.get(value_render_option='FORMATTED_VALUE'):
            for c in row:
                if any(e in S(c) for e in errs):
                    bad += 1
    print(f'\n전탭 오류 {bad}건' + ('  ← 확인 필요' if bad else '  (정상)'))
    print('완료')


if __name__ == '__main__':
    main()
