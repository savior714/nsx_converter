# 🗒️ Synology Note Station → HTML 변환기

Synology Note Station의 `.nsx` 백업 파일을 HTML 파일로 변환하는 GUI 프로그램입니다.

## ✨ 주요 기능

- 📦 `.nsx` 파일 자동 압축 해제
- 📝 JSON 형식의 노트 파일 파싱
- 🌐 HTML 파일로 변환 (깔끔하고 간편)
- 🖼️ **이미지 자동 추출 및 경로 수정 (PNG, JPG, GIF 등 모든 포맷 지원)**
- 🌐 웹 브라우저 기반 GUI 인터페이스
- 📊 실시간 변환 진행 상황 표시
- ⚡ 중복 파일명 자동 처리
- 🔧 Windows 콘솔 인코딩 문제 자동 해결

## 🚀 사용 방법

### 1. 필수 요구사항

**⚠️ Python 설치 필수!**

- **Python 3.7 이상 (필수)**
  - 다운로드: https://www.python.org/downloads/
  - **Python이 없으면 프로그램이 실행되지 않습니다**

### 2. 설치

```bash
# 저장소 클론 또는 파일 다운로드
git clone https://github.com/savior714/nsx_converter.git
cd nsx_converter

# Python 라이브러리는 기본 제공되므로 추가 설치 불필요
```

### 3. 실행

#### Windows 사용자 (가장 쉬운 방법)
`start.bat` 파일을 더블클릭하세요!

#### 명령줄 실행
```bash
python nsx_web_gui.py
```

또는

```bash
py nsx_web_gui.py
```

### 4. 사용 단계

1. **NSX 파일 경로 입력**: `.nsx` 파일의 전체 경로 입력
2. **출력 폴더 지정**: 변환된 파일을 저장할 폴더 (기본값: `converted_notes`)
3. **변환 시작**: "🔄 변환 시작" 버튼 클릭
4. **완료**: 변환 로그를 확인하고 출력 폴더에서 결과 확인

## 📂 변환 결과 구조

```
converted_notes/
├── webman/                     # 이미지 폴더 구조
│   └── 3rdparty/
│       └── NoteStation/
│           └── images/          # 이미지 파일들
│               ├── image1.jpg
│               ├── image2.png  # PNG 이미지도 정상 지원!
│               └── ...
├── 노트1.html                  # 변환된 노트 (HTML)
├── 노트2.html
└── ...
```

## 📋 변환 과정

```
.nsx 파일 → 압축 해제 → 이미지 추출 → JSON 파싱 → 
HTML 추출 및 경로 수정 → .html 파일 생성
```

## 🖼️ 이미지 처리 (최신 개선)

- **PNG, JPG, GIF, BMP, WEBP, SVG 모두 지원**
- 이미지 타입 인식 개선: `type` 필드 + 파일 확장자 모두 체크
- 같은 이미지(MD5)가 여러 파일명으로 참조되는 경우 자동 처리
- NSX 파일의 `webman` 폴더 구조가 그대로 보존되어 추출됩니다
- HTML 파일 내의 이미지 경로가 자동으로 상대 경로로 수정됩니다
- `file:///` 형식의 절대 경로가 상대 경로로 변환됩니다

## 📁 프로그램 종류

이 프로젝트는 3가지 버전의 변환기를 제공합니다:

### 1. 웹 GUI 버전 ⭐ (추천)
- **파일**: `nsx_web_gui.py`
- **실행**: `start.bat` 또는 `python nsx_web_gui.py`
- **특징**: 브라우저에서 실행되는 가장 사용하기 쉬운 버전
- **포트**: http://localhost:8080

### 2. 콘솔 버전
- **파일**: `nsx_converter_console.py`
- **실행**: `python nsx_converter_console.py`
- **특징**: 명령줄에서 실행, 서버 환경에 적합

### 3. Tkinter GUI 버전
- **파일**: `nsx_to_markdown.py`
- **실행**: `python nsx_to_markdown.py`
- **특징**: 데스크톱 GUI 애플리케이션

## ⚠️ 주의사항

- NSX 파일은 Synology Note Station에서 내보낸 백업 파일이어야 합니다
- 파일 이름에 특수문자(`\ / : * ? " < > |`)가 있으면 자동으로 `_`로 변경됩니다
- 중복된 파일 이름은 자동으로 번호가 추가됩니다 (예: `노트_1.html`, `노트_2.html`)
- 이미지는 `webman` 폴더에 저장되므로 HTML 파일과 함께 유지해야 합니다
- 변환된 파일을 이동할 때는 `webman` 폴더도 함께 이동해야 이미지가 표시됩니다

## 🐛 문제 해결

### "유효하지 않은 NSX 파일입니다"
- 파일이 손상되었거나 올바른 형식이 아닙니다
- Note Station에서 백업을 다시 내보내보세요

### "변환된 파일이 없습니다"
- NSX 파일에 노트가 포함되어 있지 않을 수 있습니다
- 로그 창에서 상세 오류 메시지를 확인하세요

### 이미지가 표시되지 않음
- 브라우저 보안 정책으로 인해 `file://` 프로토콜에서 이미지가 차단될 수 있습니다
- **추천 해결 방법**: 변환된 폴더에서 간단한 HTTP 서버 실행
  ```bash
  cd converted_notes
  python -m http.server 8000
  # 브라우저에서 http://localhost:8000 접속
  ```

## 🆕 최근 업데이트 (2025-10-17)

### v2.0 - HTML 전용 변환기로 재탄생
- ✅ **Pandoc 의존성 제거**
  - 외부 도구 설치 없이 바로 사용 가능
  - 더 빠르고 간편한 설치 및 실행
- ✅ **코드 간소화 및 안정성 향상**
  - 불필요한 변환 단계 제거
  - 더 빠른 처리 속도


### v1.5 이전 업데이트
- ✅ **PNG 파일 인식 문제 해결**
  - 이미지 타입 체크 로직 개선 (type 필드 + 파일 확장자)
  - 같은 MD5를 가진 이미지의 여러 파일명 지원
- ✅ **Windows 콘솔 인코딩 문제 해결**
  - UTF-8 강제 설정으로 이모지 출력 오류 해결
- ✅ **start.bat 배치 파일 추가**

## 📝 라이선스

MIT License

## 👤 작성자

savior714

## 🙏 기여

이슈나 PR은 언제든지 환영합니다!

---

**⭐ 이 프로젝트가 도움이 되셨다면 Star를 눌러주세요!**


