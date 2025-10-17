import os
import json
import zipfile
import shutil
from pathlib import Path
import tempfile
import re
# colorama 초기화 (Windows 색상 지원)
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    USE_COLOR = True
except ImportError:
    USE_COLOR = False
    # colorama 없이도 작동하도록 더미 객체 생성
    class Fore:
        CYAN = ""
        GREEN = ""
        YELLOW = ""
        RED = ""
    
    class Style:
        RESET_ALL = ""


def print_color(text, color=None):
    """색상 출력"""
    if USE_COLOR and color:
        print(color + text + Style.RESET_ALL)
    else:
        print(text)


def print_header():
    """헤더 출력"""
    print("\n" + "="*60)
    print_color("🗒️  Synology Note Station → HTML 변환기", Fore.CYAN)
    print("="*60 + "\n")


def sanitize_filename(name: str) -> str:
    """파일 이름으로 쓸 수 없는 문자 제거"""
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip() or "untitled"


def fix_image_paths(html_content, attachments=None):
    """HTML 내의 이미지 경로를 실제 파일명으로 수정"""
    if not attachments:
        return html_content
    
    # ref -> 파일명 매핑 생성
    ref_to_filename = {}
    for att_id, att_info in attachments.items():
        # 이미지 파일 확인 - type 필드 또는 파일 확장자로 확인
        att_type = att_info.get('type', '').lower()
        att_name = att_info.get('name', '').lower()
        
        # image/ 로 시작하는 타입이거나, 이미지 확장자를 가진 경우
        is_image = (att_type.startswith('image/') or 
                   att_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg')))
        
        if is_image:
            ref = att_info.get('ref', '')
            name = att_info.get('name', '')
            if ref and name:
                ref_to_filename[ref] = name
    
    # ref 속성이 있는 img 태그를 찾아서 src 수정
    def replace_img(match):
        full_tag = match.group(0)
        
        # ref 속성 찾기
        ref_match = re.search(r'ref="([^"]+)"', full_tag)
        if ref_match:
            ref_value = ref_match.group(1)
            if ref_value in ref_to_filename:
                # src를 실제 이미지 경로로 교체
                filename = ref_to_filename[ref_value]
                new_src = f'webman/3rdparty/NoteStation/images/{filename}'
                # src 속성 교체
                full_tag = re.sub(
                    r'src="[^"]*"',
                    f'src="{new_src}"',
                    full_tag
                )
        
        return full_tag
    
    # img 태그 전체를 찾아서 교체
    html_content = re.sub(r'<img[^>]*>', replace_img, html_content)
    
    return html_content


def get_file_path(prompt, must_exist=True):
    """파일 경로 입력 받기"""
    while True:
        print_color(prompt, Fore.YELLOW)
        path = input(">> ").strip().strip('"').strip("'")
        
        if not path:
            print_color("❌ 경로를 입력해주세요.", Fore.RED)
            continue
            
        path_obj = Path(path)
        
        if must_exist and not path_obj.exists():
            print_color(f"❌ 파일을 찾을 수 없습니다: {path}", Fore.RED)
            continue
            
        return path_obj


def convert_nsx(nsx_path, output_path):
    """NSX 파일을 HTML로 변환"""
    temp_dir = None
    
    try:
        print_color("\n🚀 변환 시작...", Fore.GREEN)
        print(f"📂 NSX 파일: {nsx_path}")
        
        # 출력 폴더 생성
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 출력 폴더: {output_dir.resolve()}\n")
        
        # 임시 폴더에 압축 해제
        temp_dir = Path(tempfile.mkdtemp())
        print_color("📦 NSX 파일 압축 해제 중...", Fore.CYAN)
        
        with zipfile.ZipFile(nsx_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        print_color("✅ 압축 해제 완료\n", Fore.GREEN)
        
        # 이미지 폴더 구조 생성
        images_dir = output_dir / "webman" / "3rdparty" / "NoteStation" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # 이미지-md5 매핑 수집 (같은 MD5에 여러 파일명 지원)
        image_mapping = {}  # {md5: [names]}
        image_count = 0
        
        print_color("🖼️  이미지 정보 수집 중...", Fore.CYAN)
        
        # 모든 노트 파일에서 attachment 정보 수집
        for folder, _, files in os.walk(temp_dir):
            for file in files:
                file_path = Path(folder) / file
                # 확장자 없는 파일만 확인 (file_로 시작하는 것 제외)
                if file_path.suffix == "" and not file_path.name.startswith('file_'):
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                        # JSON 파일인지 확인
                        if not text.strip().startswith('{'):
                            continue
                        
                        data = json.loads(text)
                        # category가 note인 것만 처리
                        if data.get('category') != 'note':
                            continue
                        
                        attachments = data.get("attachment", {})
                        if not attachments:
                            continue
                        
                        for att_id, att_info in attachments.items():
                            # 이미지 파일 확인 - type 필드 또는 파일 확장자로 확인
                            att_type = att_info.get('type', '').lower()
                            att_name = att_info.get('name', '').lower()
                            
                            # image/ 로 시작하는 타입이거나, 이미지 확장자를 가진 경우
                            is_image = (att_type.startswith('image/') or 
                                       att_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg')))
                            
                            if is_image:
                                md5 = att_info.get('md5')
                                name = att_info.get('name', 'unknown')
                                if md5 and name:
                                    if md5 not in image_mapping:
                                        image_mapping[md5] = []
                                    # 중복 방지
                                    if name not in image_mapping[md5]:
                                        image_mapping[md5].append(name)
                    except:
                        continue
        
        total_images = sum(len(names) for names in image_mapping.values())
        print_color(f"📊 {total_images}개의 이미지 정보 수집 완료 (고유 MD5: {len(image_mapping)}개)", Fore.GREEN)
        
        # file_<md5> 파일들을 모든 이미지 이름으로 복사
        print_color("📁 이미지 파일 복사 중...", Fore.CYAN)
        for folder, _, files in os.walk(temp_dir):
            for file in files:
                if file.startswith('file_'):
                    md5_hash = file.replace('file_', '')
                    if md5_hash in image_mapping:
                        source_file = Path(folder) / file
                        
                        # 같은 MD5를 가진 모든 파일명으로 복사
                        for name in image_mapping[md5_hash]:
                            target_file = images_dir / name
                            
                            try:
                                shutil.copy2(source_file, target_file)
                                image_count += 1
                            except Exception as e:
                                print_color(f"⚠️  이미지 복사 실패: {name}", Fore.YELLOW)
        
        if image_count > 0:
            print_color(f"✅ {image_count}개 이미지 파일 복사 완료\n", Fore.GREEN)
        else:
            print_color("ℹ️  이미지 파일이 없습니다\n", Fore.CYAN)
        
        # 노트 파일 찾기 및 변환
        note_count = 0
        error_count = 0
        
        print_color("🔍 노트 파일 검색 및 변환 중...\n", Fore.CYAN)
        
        for folder, _, files in os.walk(temp_dir):
            for file in files:
                file_path = Path(folder) / file
                
                # 확장자 없는 파일만 확인 (file_로 시작하는 것 제외)
                if file_path.suffix == "" and not file_path.name.startswith('file_'):
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                        
                        # JSON 파일인지 확인
                        if not text.strip().startswith('{'):
                            continue
                        
                        data = json.loads(text)
                        
                        # category가 note인 것만 처리
                        if data.get('category') != 'note':
                            continue
                        
                        # JSON 형식 확인
                        if '"content"' not in text:
                            continue
                        title = sanitize_filename(data.get("title", "untitled"))
                        html_content = data.get("content", "")
                        attachments = data.get("attachment", {})
                        
                        if not html_content:
                            continue
                        
                        # 이미지 경로 수정 (attachment 정보 전달)
                        html_content = fix_image_paths(html_content, attachments)
                        
                        # HTML 파일로 저장
                        html_file = output_dir / f"{title}.html"
                        
                        # 중복 파일명 처리
                        counter = 1
                        while html_file.exists():
                            html_file = output_dir / f"{title}_{counter}.html"
                            counter += 1
                        
                        with open(html_file, "w", encoding="utf-8") as h:
                            h.write(html_content)
                        
                        print_color(f"  ✅ {title}.html", Fore.GREEN)
                        note_count += 1
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print_color(f"  ❌ {file_path.name}: {str(e)}", Fore.RED)
                        error_count += 1
        
        # 결과 출력
        print("\n" + "="*60)
        print_color("✅ 변환 완료!", Fore.GREEN)
        print(f"📊 성공: {note_count}개 노트")
        if image_count > 0:
            print(f"🖼️  이미지: {image_count}개 (webman 폴더에 저장)")
        if error_count > 0:
            print_color(f"⚠️  실패: {error_count}개", Fore.YELLOW)
        print(f"📁 저장 위치: {output_dir.resolve()}")
        print("="*60)
        
        return True
        
    except zipfile.BadZipFile:
        print_color("\n❌ 오류: 유효하지 않은 NSX 파일입니다.", Fore.RED)
        return False
    except Exception as e:
        print_color(f"\n❌ 오류 발생: {str(e)}", Fore.RED)
        return False
    finally:
        # 임시 폴더 정리
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                print_color("\n🧹 임시 폴더 정리 완료", Fore.CYAN)
            except Exception as e:
                print_color(f"\n⚠️  임시 폴더 정리 실패: {str(e)}", Fore.YELLOW)


def main():
    print_header()
    
    # NSX 파일 경로 입력
    nsx_file = get_file_path(
        "📂 NSX 파일 경로를 입력하세요 (드래그 앤 드롭 가능):",
        must_exist=True
    )
    
    # 파일 확장자 확인
    if nsx_file.suffix.lower() != ".nxs":
        print_color("\n⚠️  경고: .nxs 파일이 아닙니다. 계속하시겠습니까? (y/n)", Fore.YELLOW)
        if input(">> ").strip().lower() != 'y':
            print_color("❌ 취소되었습니다.", Fore.RED)
            return
    
    # 출력 폴더 경로 입력
    print_color("\n📁 출력 폴더 경로를 입력하세요 (비워두면 기본값: converted_notes):", Fore.YELLOW)
    output_path = input(">> ").strip().strip('"').strip("'")
    
    if not output_path:
        output_path = Path.cwd() / "converted_notes"
    else:
        output_path = Path(output_path)
    
    # 변환 시작
    success = convert_nsx(nsx_file, output_path)
    
    if success:
        print_color("\n✨ 모든 작업이 완료되었습니다!", Fore.GREEN)
    else:
        print_color("\n❌ 변환에 실패했습니다.", Fore.RED)
    
    # 종료 대기
    print("\n엔터 키를 누르면 종료합니다...")
    input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_color("\n\n❌ 사용자가 중단했습니다.", Fore.RED)
    except Exception as e:
        print_color(f"\n❌ 예상치 못한 오류: {str(e)}", Fore.RED)
        input("\n엔터 키를 누르면 종료합니다...")

