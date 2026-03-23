# 📦 매입건 자동화 프로그램 v2.1

이커머스 셀러를 위한 매입건 처리 자동화 도구입니다.

제품 사진 폴더를 넣으면 **AI가 자동으로 분류 → 엑셀 정리 → 최저가 조회 → 상세페이지 생성 → 쿠팡 등록 데이터 준비**까지 한 번에 처리합니다.

---

## 전체 워크플로우

```
📂 사진 폴더 업로드
    ↓
[Step 1] 이미지 분석 & 제품별 폴더 자동 분류  (Claude AI)
    ↓
[Step 2] 엑셀 자동 생성 (썸네일 + 제품 정보)
    ↓
[Step 3] 네이버 쇼핑 최저가 자동 조회
    ↓
[Step 4] 상세페이지 AI 이미지 12장 생성 → 통이미지 1장 자동 합성  (Gemini AI)
    ↓
[Step 5] 쿠팡 등록 데이터 준비
```

---

## 주요 기능

### Step 1. 이미지 분석 & 폴더 분류
- Claude AI가 매입 사진을 분석하여 제품별로 자동 분류
- 제품명, 브랜드, 카테고리, 셀링포인트 자동 추출

### Step 2. 엑셀 자동 생성
- 썸네일 이미지 포함 엑셀 파일 자동 생성
- 제품 정보(제품명, 브랜드, 카테고리 등) 정리

### Step 3. 네이버 최저가 조회
- 네이버 쇼핑 API로 시장 최저가 자동 수집
- 엑셀 파일에 최저가 정보 자동 반영

### Step 4. 상세페이지 AI 이미지 생성
- Gemini AI로 상세페이지 이미지 12장 자동 생성
- 누끼컷 → 라이프스타일 배경 합성 → 상세페이지 구성
- **12장을 하나의 통이미지로 자동 합성** (쿠팡/스마트스토어 바로 업로드 가능)
- 4가지 AI 모델 선택 가능 (무료~유료)

| 모델 | 가격 | 품질 | 비고 |
|------|------|------|------|
| 나노바나나 | 무료 (하루 ~500장) | ★★★☆☆ | 기본, 가성비 |
| 나노바나나2 ⭐ | ~60원/장 | ★★★★☆ | 추천, 고품질 |
| 나노바나나 Pro | ~180원/장 | ★★★★★ | 최고 품질 |
| Imagen 4 Fast | ~27원/장 | ★★★☆☆ | 최저가, 편집불가 |

### Step 5. 쿠팡 등록 데이터 준비
- 쿠팡 OPEN API 연동
- 등록에 필요한 데이터 자동 정리

---

## 실행 방법

### 방법 1. 웹앱 (권장, 초보자용)

`웹앱실행.bat` 파일을 더블클릭하면 끝입니다.

브라우저에서 `http://localhost:8080`으로 접속하여 사용합니다.

### 방법 2. CLI (커맨드라인)

```bash
# 대화형 메뉴
python main.py

# 전체 자동 실행
python main.py --all ./사진폴더경로

# 특정 단계만 실행
python main.py --step 4 --folder ./사진폴더경로
```

### 방법 3. Step 4만 단독 실행

```bash
# 기본 (무료 모델)
python step4_detail.py --images ./사진폴더

# 추천 모델 사용
python step4_detail.py --images ./사진폴더 --model 2

# 제품명 지정 + 고해상도
python step4_detail.py --images ./사진폴더 --name "올리브오일" --model 2 --resolution 2K
```

---

## 설치 방법

### 1. Python 설치

[Python 공식 사이트](https://www.python.org/downloads/)에서 다운로드합니다.

설치 시 **"Add Python to PATH"** 반드시 체크하세요.

### 2. 프로젝트 클론

```bash
git clone https://github.com/your-username/매입자동화.git
cd 매입자동화
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. API 키 설정

`.env.example` 파일을 복사해서 `.env`로 이름을 변경한 뒤, 본인의 API 키를 입력합니다.

```bash
cp .env.example .env
```

```env
# 필수
ANTHROPIC_API_KEY=your_key_here      # https://console.anthropic.com/
GEMINI_API_KEY=your_key_here         # https://aistudio.google.com/apikey (무료)

# 선택
NAVER_CLIENT_ID=your_key_here        # https://developers.naver.com/apps
NAVER_CLIENT_SECRET=your_key_here
COUPANG_ACCESS_KEY=your_key_here     # 쿠팡 Wing → OPEN API
COUPANG_SECRET_KEY=your_key_here
COUPANG_VENDOR_ID=your_id_here
```

---

## 프로젝트 구조

```
매입자동화/
├── main.py              # 메인 실행 (CLI 메뉴)
├── webapp.py            # 웹앱 서버 (Flask)
├── config.py            # 설정 & API 키 관리
├── requirements.txt     # Python 패키지 목록
├── .env.example         # 환경변수 예시 파일
│
├── step1_classify.py    # Step 1: 이미지 분석 & 폴더 분류
├── step2_excel.py       # Step 2: 엑셀 자동 생성
├── step3_naver.py       # Step 3: 네이버 최저가 조회
├── step4_detail.py      # Step 4: 상세페이지 AI 생성 + 통이미지
├── step5_coupang.py     # Step 5: 쿠팡 등록 데이터
│
├── templates/           # HTML 템플릿
├── web_templates/       # 웹앱 템플릿
├── web_static/          # 웹앱 정적 파일
│
├── 웹앱실행.bat          # 웹앱 원클릭 실행
└── 블로그수집실행.bat     # 블로그 크롤러 실행
```

---

## 출력 결과물

프로그램 실행 후 소스 폴더 안에 다음 파일들이 생성됩니다.

```
소스폴더/
├── 제품A/               # Step 1에서 자동 분류된 폴더
├── 제품B/
├── 매입건_제품정리_날짜.xlsx   # Step 2 엑셀
└── 상세페이지/
    ├── 01_제품A/
    │   ├── 00_nukki_1.png           # 누끼컷
    │   ├── 00_lifestyle.png         # 라이프스타일
    │   ├── 01_hooking.png           # 후킹 이미지
    │   ├── 02_painpoint.png         # 고객 고민
    │   ├── ...                      # (03~12 개별 이미지)
    │   ├── 00_상세페이지_통이미지.png  # ⭐ 통이미지 (바로 업로드용)
    │   └── product_info.json        # AI 분석 결과
    └── 02_제품B/
        └── ...
```

---

## 사용 기술

- **Python 3.8+**
- **Claude AI** (Anthropic) — 이미지 분석 & 제품 분류
- **Gemini AI** (Google) — 상세페이지 이미지 생성
- **네이버 쇼핑 API** — 최저가 조회
- **쿠팡 OPEN API** — 상품 등록 데이터
- **Flask** — 웹앱 서버
- **Pillow** — 이미지 처리 & 통이미지 합성
- **openpyxl** — 엑셀 파일 생성

---

## 문제 해결

| 증상 | 해결 방법 |
|------|----------|
| `'python'은 인식되지 않는 명령` | Python 재설치 후 "Add Python to PATH" 체크 |
| 브라우저가 자동으로 안 열림 | 직접 `http://localhost:8080` 입력 |
| 화면이 변경되지 않음 | `Ctrl + Shift + R` 강제 새로고침 |
| pip 설치 실패 | 인터넷 연결 확인 후 재실행 |
| 상세페이지 이미지 텍스트 깨짐 | 모델 2(나노바나나2) 이상 사용 권장 |

---

## 주의사항

- `.env` 파일에는 API 키가 포함되어 있으므로 **절대 GitHub에 올리지 마세요**
- `.gitignore`에 이미 `.env`가 등록되어 있어 실수로 올라가지 않습니다
- 웹앱 실행 중에는 검은 창(명령 프롬프트)을 닫지 마세요

---

## 라이선스

Private — 개인 사용 목적
