# -*- coding: utf-8 -*-
"""93_콘텐츠요청(중앙데스크)에서 사용자가 선택(조사요청=TRUE)한 콘텐츠 후보를
Beauty Desk 관제판(시트1) 다음 빈 행으로 전달한다.

  python forward_content_selection.py            # 드라이런(계획만)
  python forward_content_selection.py --apply    # 반영

동작:
  1. 93_콘텐츠요청에서 B(조사요청)=TRUE 인 행을 찾는다.
  2. Beauty Desk 관제판에 같은 제목(후보1/선택한주제)이 이미 있으면 건너뛴다
     (중복 전달 방지 — 93 쪽 스키마는 건드리지 않고 관제판 쪽 제목으로 대조).
  3. 관제판 다음 빈 행에 콘텐츠ID(슬러그)·후보1·선택한주제·주요출처(93의 한줄 기획에서
     "출처: ..." 부분)를 채운다. **제작요청(F)은 FALSE로 둔다** — 중앙에서 조사요청을
     체크한 것과 실제 AI 글쓰기 시작은 별개 확인 단계로 분리한다(안전 우선).
     시작하려면 사용자가 Beauty Desk 관제판에서 제작요청을 직접 체크한다.
  4. 기존 예시 행(A열이 "안내") 등은 건드리지 않는다.

이 스크립트는 93_콘텐츠요청·관제판 시트1 외에는 아무것도 건드리지 않는다.
Add9Works·중앙데스크의 다른 탭·GAS·트리거 미접근.
"""
import sys, re, json, datetime, pathlib, os

from add9_creds import get_gspread_client

CENTRAL_ID = '1N28JERpj9Es4eTPUO_nGMYWwvRfeXQTfg72BChQEI6Q'
BEAUTY_ID = '1Q50ERfvqs16YU58gg5zRJ0kdm8N1NN9XvD52HorK6yE'

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def S(x):
    return '' if x is None else str(x)


def slugify(title, used):
    base = re.sub(r'[^\w가-힣]+', '_', title).strip('_')[:24] or '콘텐츠'
    slug, n = base, 2
    while slug in used:
        slug = f'{base}_{n}'
        n += 1
    return slug


def extract_source(one_liner):
    """93 D열(한줄 기획)의 '출처: ...' 첫 줄만 뽑는다. 없으면 전체 첫 줄."""
    for line in S(one_liner).splitlines():
        if line.strip():
            return line.strip()
    return ''


def main():
    dry = '--apply' not in sys.argv
    gc = get_gspread_client()

    central = gc.open_by_key(CENTRAL_ID)
    w93 = central.worksheet('93_콘텐츠요청')
    rows93 = w93.get('A1:H200', value_render_option='FORMATTED_VALUE')
    header93, data93 = rows93[0], rows93[1:]

    beauty = gc.open_by_key(BEAUTY_ID)
    wboard = beauty.worksheet('시트1')
    boardv = wboard.get('A1:N500', value_render_option='FORMATTED_VALUE')
    board_header, board_data = boardv[0], boardv[1:]

    existing_titles = set()
    existing_ids = set()
    last_row = 1
    for i, r in enumerate(board_data, start=2):
        if r and S(r[0]).strip():
            last_row = i
            existing_ids.add(S(r[0]).strip())
        for col in (1, 4):  # 후보1, 선택한주제
            if len(r) > col and S(r[col]).strip():
                existing_titles.add(S(r[col]).strip())

    candidates = []
    for i, r in enumerate(data93, start=2):
        r = r + [''] * (8 - len(r))
        checked = S(r[1]).strip().upper() == 'TRUE'
        title = S(r[2]).strip()
        if not checked or not title:
            continue
        if title in existing_titles:
            print(f'  건너뜀(이미 관제판에 있음): {title}')
            continue
        candidates.append(dict(row93=i, title=title, one_liner=S(r[3]), type_=S(r[4])))

    print(f'93_콘텐츠요청 선택(조사요청=TRUE) {sum(1 for r in data93 if S((r+[""]*8)[1]).strip().upper()=="TRUE")}건 '
          f'중 신규 전달 대상 {len(candidates)}건')

    if not candidates:
        print('전달할 신규 항목 없음. 종료')
        return

    plan = []
    for c in candidates:
        slug = slugify(c['title'], existing_ids)
        existing_ids.add(slug)
        source = extract_source(c['one_liner'])
        plan.append([slug, c['title'], '', '', c['title'], False,
                     '제작요청 대기', '', '', '', '', '', source, ''])
        print(f"  [행{c['row93']}] {slug} <- {c['title'][:40]}")

    if dry:
        print('\n드라이런. --apply 로 반영 (제작요청은 FALSE로 생성 — Beauty Desk에서 사용자가 직접 시작)')
        return

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    snapdir = pathlib.Path(os.environ.get('TEMP', '.')) / 'add9_central_snapshots'
    snapdir.mkdir(parents=True, exist_ok=True)
    (snapdir / f'beauty_board_before_{stamp}.json').write_text(
        json.dumps(boardv, ensure_ascii=False), encoding='utf-8')

    start = last_row + 1
    wboard.update(range_name=f'A{start}:N{start+len(plan)-1}', values=plan,
                  value_input_option='USER_ENTERED')
    print(f'\n관제판 {start}~{start+len(plan)-1}행에 {len(plan)}건 반영')
    print(f'스냅샷: beauty_board_before_{stamp}.json')
    print('다음: 사용자가 Beauty Desk 관제판에서 해당 행의 "제작요청"을 체크하면 파이프라인 시작')


if __name__ == '__main__':
    main()
