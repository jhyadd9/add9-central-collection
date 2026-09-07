# add9-central-collection

ADD9 중앙데스크 시트(`1N28JER…`)에 세 줄기 후보를 수집·반영하는 자동화 코드.
클라우드 루틴(claude.ai/code/routines)이 이 저장소를 clone 해서 돌린다. 로컬에서도 그대로 돈다.

## 파일

| 파일 | 역할 |
|---|---|
| `central_desk_round.py` | 수집한 payload.json 을 P0·94·91 에 반영, P1 시작값 전환 |
| `central_desk_fit_heights.py` | 회차 반영 직후 P1 행높이 맞추기 (폰 잘림 방지, 필수) |
| `forward_content_selection.py` | 93_콘텐츠요청 선택건 → Beauty Desk 관제판 전달 (수동/온디맨드) |
| `add9_creds.py` | 서비스 계정 자격증명 로더 (로컬 파일 / 클라우드 환경변수 둘 다) |
| `COLLECTION_PLAYBOOK.md` | 수집 실행 지침 **사본**. 정본은 OneDrive `ADD9_OS/SHARED_SYSTEM/COLLECTION_PLAYBOOK.md` |

## 자격증명

`add9_creds.py` 가 아래 순서로 찾는다:

1. `ADD9_SA_JSON` 환경변수 — 서비스 계정 JSON **전체 문자열** (클라우드 루틴용)
2. `ADD9_SA_CRED` 환경변수 — 키 파일 절대경로
3. `C:\BeautyDesk\credentials\service-account.json` (집 PC)
4. `~/.add9/service-account.json` (그 외 PC)

**키 파일·JSON 을 이 저장소에 커밋하지 않는다.** `.gitignore` 가 `*.json`·`*.pem`·`.env` 를 막는다.
클라우드는 claude.ai 환경 설정의 시크릿으로 `ADD9_SA_JSON` 을 넣는다.

## 클라우드 루틴 3개

| 루틴 | 줄기 | cron (UTC) | 한국시간 |
|---|---|---|---|
| add9-market-signal | signals | `20 22 * * *` | 매일 07:20 |
| add9-product-candidate | products | `40 22 * * 0,2,4` | 월·수·금 07:40 |
| add9-beauty-topic | contents | `10 23 * * 1,3,5` | 화·목·토 08:10 |

각 루틴은 자기 줄기 3건만 수집해 payload 로 만들고 `central_desk_round.py --apply` → `central_desk_fit_heights.py --apply` 순으로 반영한다. 절차·문체·필드 규칙은 `COLLECTION_PLAYBOOK.md` 를 런타임에 읽어 따른다.

**안전장치**: 후보 등록까지만 자동. 콘텐츠 선택 체크박스·소싱 확정·발행은 사람이 한다. 근거 있는 3건을 못 만들면 억지로 채우지 않고 보고만 한다. 반영 전 전체 스냅샷을 남긴다. 같은 회차·같은 줄기가 이미 있으면 중단한다.

## 수동 실행

```bash
pip install -r requirements.txt
# ADD9_SA_JSON 또는 로컬 키 파일 준비
python central_desk_round.py payload.json            # 드라이런
python central_desk_round.py payload.json --apply
python central_desk_fit_heights.py --apply
```

## 플레이북 동기화

`COLLECTION_PLAYBOOK.md` 는 OneDrive 정본의 **사본**이다. OneDrive 쪽이 바뀌면 이 사본도 갱신해 push 한다. (정본 헤더에도 이 주의가 있다.)

## 로컬 스케줄과의 관계

이전에는 집 PC 로컬 스케줄(`~/.claude/scheduled-tasks/add9-*`)이 돌렸다. 클라우드 루틴이 검증되면 로컬 스케줄을 비활성화한다. **둘을 동시에 켜지 않는다** — 중복 방지 장치가 있지만 운영 방식이 아니다.
