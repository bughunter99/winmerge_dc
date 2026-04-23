# WinMerge -> Python(PySide6) 5단계 변환 계획

## 목표
- 원본 WinMerge의 핵심 클래스 구조와 데이터 흐름을 최대한 동일하게 유지한다.
- UI 프레임워크는 PySide6를 사용한다.
- 전환 초반에는 기능 확장보다 "동작 동등성(behavioral parity)"을 우선한다.

## 분석 요약(원본 기준)
- 앱 진입/초기화: Src/Merge.cpp 의 CMergeApp 초기화 루틴
- 메인 프레임/문서 오픈 라우팅: Src/MainFrm.h 의 CMainFrame
- 텍스트 비교 문서 모델: Src/MergeDoc.h 의 CMergeDoc
- 폴더 비교 문서 모델: Src/DirDoc.h 의 CDirDoc
- 비교 컨텍스트(상태/옵션/결과): Src/DiffContext.h 의 CDiffContext
- 비교 엔진 래퍼: Src/DiffWrapper.h 의 CDiffWrapper, Src/CompareEngines/Wrap_DiffUtils.h 의 CompareEngines::DiffUtils
- 비동기 폴더 비교 스레드: Src/DiffThread.h 의 CDiffThread

## Python 패키지 구조(원본 클래스 대응)
- pyversion/app/
  - app.py: CMergeApp 대응(초기화/설정/명령행/싱글인스턴스 정책)
  - main_window.py: CMainFrame 대응(문서 오픈 라우팅, 메뉴/액션)
- pyversion/core/
  - diff_context.py: CDiffContext 대응
  - diff_wrapper.py: CDiffWrapper 대응
  - diff_thread.py: CDiffThread 대응
  - compare_engines/
    - diffutils_engine.py: CompareEngines::DiffUtils 대응
    - byte_compare.py, binary_compare.py, image_compare.py, time_size_compare.py, existence_compare.py
- pyversion/docs/
  - merge_doc.py: CMergeDoc 대응
  - dir_doc.py: CDirDoc 대응
  - hex_doc.py: CHexMergeDoc 대응(2차)
- pyversion/ui/
  - merge_views.py, dir_views.py, location_view.py (Qt Widget/View 계층)
- pyversion/plugins/
  - plugin_manager.py, file_transform.py
- pyversion/services/
  - options_service.py, path_service.py, encoding_service.py, report_service.py

## 원본 데이터 흐름 유지 설계
1) 파일/폴더 열기 요청
- 원본: CMainFrame::DoFileOrFolderOpen/Show*Doc -> 문서 객체 생성
- Python: MainWindow.open_targets() -> 문서 팩토리(merge_doc/dir_doc) 생성

2) 비교 설정/필터/플러그인 결합
- 원본: CDiffContext(옵션, 필터, 플러그인 정보)
- Python: DiffContext(dataclass) + FilterList/SubstitutionList + PluginInfosProvider

3) 비교 실행
- 텍스트/파일: DiffWrapper.run_file_diff()
- 폴더: DiffThread(compare collect + compare phase)
- Python: 동일하게 "수집 단계 -> 비교 단계" 2단계 파이프라인 유지

4) 결과 모델 업데이트
- 원본: DiffList / DiffItemList / CompareStats 갱신
- Python: DiffListModel / DiffItemModel / CompareStatsModel 갱신

5) UI 반영
- 원본: 문서(View) 업데이트, 상태바/위치뷰/동기 스크롤
- Python: Qt signal/slot으로 doc_changed, diff_ready, status_changed 이벤트 전달

## 5단계 전환 로드맵

### 1단계: 부트스트랩 + 골격 이식 (1~2주)
- 목표
  - PySide6 앱 실행, 메인 윈도우/메뉴/오픈 다이얼로그 동작
  - 원본 클래스 이름을 Python 클래스명으로 최대한 대응
- 작업
  - Python 3.11+ 환경 고정
  - 기본 패키지 구조 생성
  - App/MainWindow/Document 추상 계층 작성
- 완료 기준
  - 2-way/3-way 파일 선택 후 빈 문서 탭 생성까지 동작

### 2단계: 텍스트 비교 핵심 이식 (2~4주)
- 목표
  - CMergeDoc + CDiffWrapper의 핵심 기능 1차 동등성 확보
- 작업
  - 텍스트 로딩(인코딩 처리), 라인 단위 diff, 기본 병합(copy left/right)
  - DiffContext 옵션(공백 무시, 대소문자 무시 등) 반영
  - 변경 결과 모델(DiffList) 구축
- 완료 기준
  - 샘플 케이스에서 원본과 diff 개수/탐색 순서가 대부분 일치

### 3단계: 폴더 비교 + 스레딩 이식 (3~5주)
- 목표
  - CDirDoc + CDiffThread 기반 폴더 비교 파이프라인 재현
- 작업
  - 수집 단계(디렉터리 트래버스) + 비교 단계(파일별 엔진 호출) 분리
  - Qt의 QThread/QThreadPool로 중단/일시정지/재개 구현
  - CompareStats/리포트/필터 적용
- 완료 기준
  - 대규모 폴더 비교에서 진행률/중단/재개가 안정적으로 동작

### 4단계: 고급 기능(플러그인/이미지/바이너리/웹) 이식 (4~8주)
- 목표
  - 엔진 확장과 문서 타입별 프레임 동작 호환성 확보
- 작업
  - Binary/Image/TimeSize/Existence 엔진 우선 이식
  - 플러그인 파이프라인(언팩/프리디프) Python 인터페이스화
  - Hex/Image/Web 문서 타입 순차 이식
- 완료 기준
  - 주요 메뉴 시나리오(파일/폴더/이미지 비교)가 end-to-end 수행

### 5단계: 동등성 검증 + 패키징 (2~4주)
- 목표
  - 회귀 테스트와 배포 가능한 실행 패키지 확보
- 작업
  - 원본 대비 회귀 테스트 세트 구축(동일 입력/동일 결과 검증)
  - 성능 튜닝(큰 파일/대용량 폴더)
  - PyInstaller 기반 배포 아티팩트 생성
- 완료 기준
  - 핵심 사용자 시나리오 pass, 크래시/데드락/데이터 손실 이슈 0건

## workon v1 가상환경 기준 실행 원칙
- 전환 개발/테스트 명령은 항상 v1 환경에서 실행한다.
- 예시 순서
  1. workon v1
  2. python -m pip install -U pip
  3. python -m pip install pyside6
  4. python -m pip install -r pyversion/requirements.txt

## 위험요소 및 대응
- diff 알고리즘 미세 차이로 결과 불일치 가능
  - 대응: Golden test(원본 출력 스냅샷) 기반 비교
- MFC 이벤트 모델과 Qt 이벤트 모델 차이
  - 대응: 문서 상태 변경 이벤트를 명시적 signal로 표준화
- 멀티스레드 UI 갱신 경합
  - 대응: 백그라운드 스레드에서 모델만 갱신, UI는 메인 스레드에서 반영

## 우선순위 권장
- 1순위: 텍스트/폴더 비교 동등성
- 2순위: 플러그인/필터 파이프라인
- 3순위: 이미지/웹/헥사 비교
