import os
import zipfile
import xml.etree.ElementTree as ET
import shutil
import base64
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser
import customtkinter as ctk
from PIL import Image

# Настройка внешнего вида (только светлая тема)
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# --- Парсер BCF (без изменений) ---
class BCFParser:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.temp_dir = os.path.join(os.getcwd(), "temp_bcf")
        os.makedirs(self.output_dir, exist_ok=True)

    def parse_bcf(self, bcf_path):
        issues = []
        with zipfile.ZipFile(bcf_path) as archive:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            os.makedirs(self.temp_dir)
            archive.extractall(self.temp_dir)
            markup_files = self._find_markup_files()
            for markup_file in markup_files:
                issue = self._parse_markup_file(markup_file)
                if issue:
                    issues.append(issue)
        shutil.rmtree(self.temp_dir)             
        return issues

    def _find_markup_files(self):
        markup_files = []
        for root, _, files in os.walk(self.temp_dir):
            for file in files:
                if file == "markup.bcf":
                    markup_files.append(os.path.join(root, file))
        return markup_files

    def _parse_markup_file(self, markup_file):
        try:
            tree = ET.parse(markup_file)
            root = tree.getroot()
            ns = {'ns': root.tag.split('}')[0][1:]} if '}' in root.tag else {'ns': ''}
            folder_guid = os.path.basename(os.path.dirname(markup_file))
            topic = root.find("ns:Topic", ns) or root.find("Topic")
            if topic is None:
                return None
            topic_data = self._parse_topic(topic, ns)
            topic_data.update(self._parse_comments(root, ns))
            viewpoint_dir = os.path.dirname(markup_file)
            viewpoints_data = root.find("ns:Viewpoints", ns) or root.find("Viewpoints")
            if viewpoints_data is not None:
                viewpoints = self._parse_viewpoints(viewpoints_data, ns, viewpoint_dir, folder_guid)
                if viewpoints:
                    topic_data['viewpoints'] = viewpoints
            return {
                'folder_guid': folder_guid,
                'topic': topic_data
            }
        except Exception as e:
            return None

    def _parse_topic(self, topic, ns):
        topic_data = {**topic.attrib}
        for elem_name in ['Title', 'Priority', 'Index', 'CreationDate', 'CreationAuthor']:
            elem = topic.find(f"ns:{elem_name}", ns) or topic.find(elem_name)
            if elem is not None and elem.text:
                topic_data[elem_name.lower()] = elem.text
        return topic_data

    def _parse_comments(self, root, ns):
        result = {}
        comments = []
        for comment in root.findall("ns:Comment", ns) or root.findall("Comment"):
            comment_data = {**comment.attrib}
            comment_text = comment.find("ns:Comment", ns) or comment.find("Comment")
            if comment_text is not None and comment.text:
                comment_data['text'] = comment_text.text
            viewpoint = comment.find("ns:Viewpoint", ns) or comment.find("Viewpoint")
            if viewpoint is not None:
                comment_data['viewpoint'] = viewpoint.attrib
            comments.append(comment_data)
        if comments:
            result['comments'] = comments
        return result

    def _parse_viewpoints(self, viewpoints_data, ns, viewpoint_dir, folder_guid):
        viewpoints = []
        viewpoints_guid = viewpoints_data.get('Guid')
        vp_data = {
            'Guid': viewpoints_guid,
            'viewpoint': viewpoints_data.find("ns:Viewpoint", ns).text if viewpoints_data.find("ns:Viewpoint", ns) is not None else 'viewpoint.bcfv',
            'snapshot': viewpoints_data.find("ns:Snapshot", ns).text if viewpoints_data.find("ns:Snapshot", ns) is not None else 'snapshot.png'
        }
        viewpoint_file = os.path.join(viewpoint_dir, vp_data['viewpoint'])
        if os.path.exists(viewpoint_file):
            components = self._parse_viewpoint_file(viewpoint_file)
            if components:
                vp_data['components'] = components
        snapshot_path = os.path.join(viewpoint_dir, vp_data['snapshot'])
        if os.path.exists(snapshot_path):
            with open(snapshot_path, "rb") as image_file:
                vp_data['snapshot_base64'] = base64.b64encode(image_file.read()).decode('utf-8')
        viewpoints.append(vp_data)
        return viewpoints

    def _parse_viewpoint_file(self, viewpoint_file):
        try:
            vp_tree = ET.parse(viewpoint_file)
            vp_root = vp_tree.getroot()
            components = []
            components_section = vp_root.find('Components')
            if components_section is not None:
                exceptions = components_section.find('Visibility/Exceptions')
                if exceptions is not None:
                    for comp in exceptions.findall('Component'):
                        if 'IfcGuid' in comp.attrib:
                            components.append({
                                'guid': comp.attrib['IfcGuid'],
                                'source': 'visibility_exceptions'
                            })
                coloring = components_section.find('Coloring/Color')
                if coloring is not None:
                    for comp in coloring.findall('Component'):
                        if 'IfcGuid' in comp.attrib:
                            components.append({
                                'guid': comp.attrib['IfcGuid'],
                                'source': 'coloring'
                            })
            return components
        except Exception as e:
            return None

# --- Генератор HTML-отчета (без изменений) ---
class ReportGenerator:
    @staticmethod
    def create_html_report(issues, output_file, css_path=None):
        html_content = ReportGenerator._generate_html_content(issues, css_path)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    @staticmethod
    def _generate_html_content(issues, css_path=None):
        css_link = ""
        if css_path:
            css_filename = os.path.basename(css_path)
            css_link = f'<link rel="stylesheet" href="{css_filename}">'
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>BCF Report</title>
    {css_link}
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .viewpoint-container {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .snapshot {{
            width: 300px;
            height: auto;
            border: 1px solid #ccc;
        }}
        .component {{
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <h1>BCF Report (part of the imchecker service)</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    {''.join(ReportGenerator._generate_issue_html(issue) for issue in issues)}
</body>
</html>"""

    @staticmethod
    def _generate_issue_html(issue):
        topic = issue['topic']
        return f"""
<div class="issue">
    <h2>{topic.get('title', 'No title')}</h2>
    <p>GUID: {issue['folder_guid']}</p>
    {ReportGenerator._generate_viewpoints_html(topic)}
    {ReportGenerator._generate_comments_html(topic)}
</div>"""

    @staticmethod
    def _generate_viewpoints_html(topic):
        if 'viewpoints' not in topic:
            return ""
        content = []
        for vp in topic['viewpoints']:
            snapshot_html = ""
            components_html = ""
            if 'snapshot_base64' in vp:
                snapshot_html = f'<img class="snapshot" src="data:image/png;base64,{vp["snapshot_base64"]}" alt="Viewpoint snapshot">'
            if 'components' in vp and vp['components']:
                unique_components = {c['guid'] for c in vp['components']}
                components_html = f"""
            <div class="components-column">
                <h4>GUID IFC Components:</h4>
                <div class="components-list">
                    {''.join(f'<div class="component">{guid}</div>' for guid in sorted(unique_components))}
                </div>
            </div>"""
            content.append(f"""
        <div class="viewpoint-container">
            <div class="snapshot-container">
                {snapshot_html}
            </div>
            {components_html}
        </div>""")
        return "\n".join(content)

    @staticmethod
    def _generate_comments_html(topic):
        if 'comments' not in topic:
            return ""
        return f"""
    <div>
        <h3>Comments:</h3>
        {''.join(f'''
        <div class="comment">
            <div><strong>{c.get('Author', 'Unknown')}</strong> - {c.get('Date', 'No date')}</div>
            <p>{c.get('text', 'No text')}</p>
        </div>''' for c in topic['comments'])}
    </div>"""

# --- Упрощенный GUI интерфейс ---
class BCFParserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.selected_bcf_file = None
        self.output_dir = "output"
        
        self.title("BCF Parser")
        self.geometry("500x300")
        self.minsize(400, 250)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Основной фрейм
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Заголовок
        self.title_label = ctk.CTkLabel(
            self.main_frame, 
            text="BCF Parser", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=(10, 20))
        
        # Кнопка выбора файла
        self.select_button = ctk.CTkButton(
            self.main_frame,
            text="Выбрать BCF файл",
            command=self.select_bcf_file,
            corner_radius=8,
            height=50,
            font=ctk.CTkFont(size=16)
        )
        self.select_button.pack(fill="x", padx=50, pady=5)
        
        # Кнопка генерации отчета
        self.generate_button = ctk.CTkButton(
            self.main_frame,
            text="Сгенерировать и открыть HTML отчет",
            command=self.generate_and_open_report,
            corner_radius=8,
            height=50,
            state="disabled",
            font=ctk.CTkFont(size=16)
        )
        self.generate_button.pack(fill="x", padx=50, pady=5)

        # Добавляем подвал
        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer_frame.pack(side="bottom", fill="x", pady=(20, 10))
        
        self.smg_label = ctk.CTkLabel(
            self.footer_frame,
            text="SMG",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.smg_label.pack(side="right", padx=10)
    
    def select_bcf_file(self):
        """Обработчик кнопки: выбор BCF файла через диалог"""
        file_path = filedialog.askopenfilename(filetypes=[("BCF Files", "*.bcf")])
        if file_path:
            self.selected_bcf_file = file_path
            self.generate_button.configure(state="normal")
    
    def generate_and_open_report(self):
        """Обработчик кнопки: формирует и открывает HTML-отчет"""
        if not self.selected_bcf_file:
            messagebox.showwarning("Ошибка", "Сначала загрузите BCF-файл.")
            return
        
        try:
            css_file = "styles.css"
            os.makedirs(self.output_dir, exist_ok=True)

            if os.path.exists(css_file):
                shutil.copy2(css_file, os.path.join(self.output_dir, os.path.basename(css_file)))

            parser = BCFParser(self.output_dir)
            issues = parser.parse_bcf(self.selected_bcf_file)

            report_file = os.path.join(self.output_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            ReportGenerator.create_html_report(issues, report_file, css_file)

            webbrowser.open_new_tab(report_file)
            messagebox.showinfo("Успешно", f"Отчет создан и открыт в браузере:\n{report_file}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}")

# --- Запуск приложения ---
if __name__ == "__main__":
    app = BCFParserApp()
    app.mainloop()