import os
import json
import zipfile
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from threading import Thread
import tempfile
import re


class NsxConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Synology Note Station → HTML 변환기")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        self.nsx_file = None
        self.output_dir = None
        self.is_running = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # 상단 프레임
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)
        
        # NSX 파일 선택
        tk.Label(top_frame, text="NSX 파일:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.nsx_entry = tk.Entry(top_frame, width=50)
        self.nsx_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(top_frame, text="찾아보기", command=self.select_nsx_file).grid(row=0, column=2, pady=5)
        
        # 출력 폴더 선택
        tk.Label(top_frame, text="출력 폴더:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_entry = tk.Entry(top_frame, width=50)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5)
        self.output_entry.insert(0, str(Path.cwd() / "converted_notes"))
        tk.Button(top_frame, text="찾아보기", command=self.select_output_dir).grid(row=1, column=2, pady=5)
        
        # 변환 버튼
        button_frame = tk.Frame(self.root, padx=10, pady=10)
        button_frame.pack(fill=tk.X)
        
        self.convert_btn = tk.Button(
            button_frame, 
            text="🔄 변환 시작", 
            font=("Arial", 12, "bold"),
            bg="#4CAF50", 
            fg="white",
            command=self.start_conversion,
            height=2
        )
        self.convert_btn.pack(fill=tk.X)
        
        # 진행률 표시
        progress_frame = tk.Frame(self.root, padx=10, pady=5)
        progress_frame.pack(fill=tk.X)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X)
        
        # 로그 창
        log_frame = tk.Frame(self.root, padx=10, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(log_frame, text="📝 변환 로그:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=15, 
            font=("Consolas", 9),
            bg="#f0f0f0"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message):
        """로그 메시지 추가"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
        
    def select_nsx_file(self):
        """NSX 파일 선택"""
        file_path = filedialog.askopenfilename(
            title="NSX 파일 선택",
            filetypes=[("NSX 파일", "*.nxs"), ("모든 파일", "*.*")]
        )
        if file_path:
            self.nsx_entry.delete(0, tk.END)
            self.nsx_entry.insert(0, file_path)
            
    def select_output_dir(self):
        """출력 폴더 선택"""
        dir_path = filedialog.askdirectory(title="출력 폴더 선택")
        if dir_path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, dir_path)
    
    def fix_image_paths(self, html_content, attachments=None):
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
            
    def sanitize_filename(self, name: str) -> str:
        """파일 이름으로 쓸 수 없는 문자 제거"""
        invalid = r'\/:*?"<>|'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip() or "untitled"
        
    def start_conversion(self):
        """변환 시작"""
        if self.is_running:
            messagebox.showwarning("경고", "이미 변환이 진행 중입니다.")
            return
            
        nsx_path = self.nsx_entry.get().strip()
        output_path = self.output_entry.get().strip()
        
        if not nsx_path or not Path(nsx_path).exists():
            messagebox.showerror("오류", "유효한 NSX 파일을 선택해주세요.")
            return
            
        if not output_path:
            messagebox.showerror("오류", "출력 폴더를 지정해주세요.")
            return
                
        # 별도 스레드에서 변환 실행
        self.is_running = True
        self.convert_btn.config(state=tk.DISABLED)
        self.progress_bar.start()
        self.log_text.delete(1.0, tk.END)
        
        thread = Thread(target=self.convert, args=(nsx_path, output_path))
        thread.start()
        
    def convert(self, nsx_path, output_path):
        """실제 변환 작업"""
        temp_dir = None
        
        try:
            self.log("🚀 변환 시작...")
            self.log(f"📂 NSX 파일: {nsx_path}")
            
            # 출력 폴더 생성
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"📁 출력 폴더: {output_dir.resolve()}")
            
            # 임시 폴더에 압축 해제
            temp_dir = Path(tempfile.mkdtemp())
            self.log(f"\n📦 NSX 파일 압축 해제 중...")
            
            with zipfile.ZipFile(nsx_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
            self.log(f"✅ 압축 해제 완료")
            
            # 이미지 폴더 구조 생성
            images_dir = output_dir / "webman" / "3rdparty" / "NoteStation" / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # 이미지-md5 매핑 수집 (같은 MD5에 여러 파일명 지원)
            image_mapping = {}  # {md5: [names]}
            image_count = 0
            
            self.log("\n🖼️ 이미지 정보 수집 중...")
            
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
            self.log(f"📊 {total_images}개의 이미지 정보 수집 완료 (고유 MD5: {len(image_mapping)}개)")
            
            # file_<md5> 파일들을 모든 이미지 이름으로 복사
            self.log("📁 이미지 파일 복사 중...")
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
                                    self.log(f"⚠️ 이미지 복사 실패: {name}")
            
            if image_count > 0:
                self.log(f"✅ {image_count}개 이미지 파일 복사 완료")
            else:
                self.log("ℹ️ 이미지 파일이 없습니다")
            
            # 노트 파일 찾기 및 변환
            note_count = 0
            error_count = 0
            
            self.log("\n🔍 노트 파일 검색 및 변환 중...\n")
            
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
                            
                            if '"content"' not in text:
                                continue
                            title = self.sanitize_filename(data.get("title", "untitled"))
                            html_content = data.get("content", "")
                            attachments = data.get("attachment", {})
                            
                            if not html_content:
                                continue
                            
                            # 이미지 경로 수정 (attachment 정보 전달)
                            html_content = self.fix_image_paths(html_content, attachments)
                            
                            # HTML 파일로 저장
                            html_file = output_dir / f"{title}.html"
                            
                            counter = 1
                            while html_file.exists():
                                html_file = output_dir / f"{title}_{counter}.html"
                                counter += 1
                            
                            with open(html_file, "w", encoding="utf-8") as h:
                                h.write(html_content)
                            
                            self.log(f"✅ {title}.html")
                            note_count += 1
                        
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            self.log(f"❌ {file_path.name}: {str(e)}")
                            error_count += 1
            
            # 결과 출력
            self.log("\n" + "="*50)
            self.log(f"✅ 변환 완료! 성공: {note_count}개 노트")
            if image_count > 0:
                self.log(f"🖼️ 이미지: {image_count}개 (webman 폴더에 저장)")
            if error_count > 0:
                self.log(f"⚠️ 실패: {error_count}개")
            self.log(f"📁 저장 위치: {output_dir.resolve()}")
            self.log("="*50)
            
            messagebox.showinfo(
                "변환 완료", 
                f"✅ {note_count}개 노트가 변환되었습니다.\n\n"
                f"📁 {output_dir.resolve()}"
            )
            
        except zipfile.BadZipFile:
            self.log("\n❌ 오류: 유효하지 않은 NSX 파일입니다.")
            messagebox.showerror("오류", "유효하지 않은 NSX 파일입니다.")
        except Exception as e:
            self.log(f"\n❌ 오류 발생: {str(e)}")
            messagebox.showerror("오류", f"변환 중 오류가 발생했습니다:\n{str(e)}")
        finally:
            # 임시 폴더 정리
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self.log(f"\n🧹 임시 폴더 정리 완료")
                except Exception as e:
                    self.log(f"\n⚠️  임시 폴더 정리 실패: {str(e)}")
            
            self.is_running = False
            self.convert_btn.config(state=tk.NORMAL)
            self.progress_bar.stop()


def main():
    root = tk.Tk()
    app = NsxConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

