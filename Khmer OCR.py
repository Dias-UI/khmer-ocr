from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from googletrans import Translator
from tkinter import ttk
import fitz  # PyMuPDF
import re
import os

# Global variables
translator = Translator()
current_text = {"original": "", "translated": "", "is_mixed": False}
current_page = 0
total_pages = 0
pdf_pages = []
current_lang = None

def clean_khmer_text(text):
    """Remove stray characters and improve Khmer text quality"""
    # Remove common OCR artifacts
    text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FF\u0020-\u007E\n\r\t]', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove standalone punctuation marks that are likely errors
    text = re.sub(r'\n[^\w\u1780-\u17FF]+\n', '\n', text)
    
    return text.strip()

def preprocess_image(image):
    """Enhanced image preprocessing for better OCR accuracy"""
    # Convert to grayscale
    image = image.convert('L')
    
    # Apply slight blur to reduce noise
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    # Enhance contrast more aggressively
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)
    
    # Apply threshold to create cleaner black and white image
    threshold = 128
    image = image.point(lambda p: 255 if p > threshold else 0)
    
    return image

def toggle_language():
    # Simple toggle between original and translated text
    if text_widget.get("1.0", tk.END).strip() == current_text["original"].strip():
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, current_text["translated"])
        toggle_button.config(text="Show Original")
    else:
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, current_text["original"])
        toggle_button.config(text="Show Translation")

def navigate_page(direction):
    """Navigate between PDF pages"""
    global current_page
    if not pdf_pages:
        return
    
    current_page += direction
    if current_page < 0:
        current_page = 0
    elif current_page >= total_pages:
        current_page = total_pages - 1
    
    process_pdf_page(current_page, current_lang)

def update_page_label():
    """Update the page navigation label"""
    if total_pages > 0:
        page_label.config(text=f"Page {current_page + 1} of {total_pages}")
        prev_button.config(state=tk.NORMAL if current_page > 0 else tk.DISABLED)
        next_button.config(state=tk.NORMAL if current_page < total_pages - 1 else tk.DISABLED)
        page_nav_frame.pack(pady=5)
    else:
        page_nav_frame.pack_forget()

def process_pdf_page(page_num, lang):
    """Process a specific page from the loaded PDF"""
    global current_text, current_page
    
    try:
        if page_num >= len(pdf_pages):
            return
        
        current_page = page_num
        image = pdf_pages[page_num]
        
        # Preprocess the image
        image = preprocess_image(image)
        
        # Use pytesseract to extract text
        extracted_text = pytesseract.image_to_string(image, lang=lang, config='--psm 6')
        
        # Clean the text if it's Khmer
        if 'khm' in lang:
            extracted_text = clean_khmer_text(extracted_text)
        
        # Store original text
        current_text["original"] = extracted_text
        current_text["is_mixed"] = (lang == 'khm+eng')
        
        # Translate text based on the language mode
        if lang == 'khm':
            current_text["translated"] = translator.translate(extracted_text, src='km', dest='en').text
        elif lang == 'eng':
            current_text["translated"] = translator.translate(extracted_text, src='en', dest='km').text
        elif lang == 'khm+eng':
            current_text["translated"] = translator.translate(extracted_text, src='km', dest='en').text
        
        # Display the original text
        text_widget.delete('1.0', tk.END)
        text_widget.insert(tk.END, current_text["original"])
        
        # Show toggle button
        toggle_button.pack(pady=5)
        separator.pack(fill='x', padx=10, pady=5)
        toggle_button.config(text="Show Translation")
        
        # Update page navigation
        update_page_label()
        
    except Exception as e:
        messagebox.showerror("Error", f"Error processing page {page_num + 1}: {str(e)}")

def load_pdf(filepath, lang):
    """Load all pages from a PDF file"""
    global pdf_pages, total_pages, current_page, current_lang
    
    try:
        pdf_pages = []
        current_lang = lang
        
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(filepath)
        total_pages = len(pdf_document)
        
        # Convert each page to an image
        for page_num in range(total_pages):
            page = pdf_document[page_num]
            # Render page to an image with higher resolution for better OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pdf_pages.append(img)
        
        pdf_document.close()
        
        # Process the first page
        current_page = 0
        process_pdf_page(0, lang)
        
    except Exception as e:
        messagebox.showerror("Error", f"Error loading PDF: {str(e)}")
        pdf_pages = []
        total_pages = 0

def handle_drop(event, lang):
    # Get the dropped file path
    try:
        file_path = event.data
        if file_path.startswith('{'):  # Windows workaround
            file_path = file_path.strip('{}')
        
        # Check if it's a PDF or image
        if file_path.lower().endswith('.pdf'):
            load_pdf(file_path, lang)
        else:
            process_image(6, lang, file_path)
        
        event.widget.configure(bg="#303030")  # Reset color
    except Exception as e:
        messagebox.showerror("Error", str(e))

def handle_drag_enter(event):
    event.widget.configure(bg="#505050")  # Highlight effect

def handle_drag_leave(event):
    event.widget.configure(bg="#303030")  # Reset color

def process_image(psm_mode, lang, filepath=None):
    global pdf_pages, total_pages, current_page, current_lang
    
    try:
        if filepath is None:
            filepath = filedialog.askopenfilename(
                filetypes=[
                    ("All Supported Files", "*.jpg;*.jpeg;*.png;*.bmp;*.pdf"),
                    ("Image Files", "*.jpg;*.jpeg;*.png;*.bmp"),
                    ("PDF Files", "*.pdf")
                ]
            )
        if not filepath:
            return
        
        # Check if it's a PDF
        if filepath.lower().endswith('.pdf'):
            load_pdf(filepath, lang)
            return
        
        # Reset PDF state for single images
        pdf_pages = []
        total_pages = 0
        current_page = 0
        current_lang = lang
        update_page_label()
        
        # Open the image
        image = Image.open(filepath)
        
        # Preprocess the image
        image = preprocess_image(image)
        
        # Use pytesseract to extract text from the image
        extracted_text = pytesseract.image_to_string(image, lang=lang, config=f'--psm {psm_mode}')
        
        # Clean the text if it's Khmer
        if 'khm' in lang:
            extracted_text = clean_khmer_text(extracted_text)
        
        # Store original text
        current_text["original"] = extracted_text
        current_text["is_mixed"] = (lang == 'khm+eng')
        
        # Translate text based on the language mode
        if lang == 'khm':
            current_text["translated"] = translator.translate(extracted_text, src='km', dest='en').text
        elif lang == 'eng':
            current_text["translated"] = translator.translate(extracted_text, src='en', dest='km').text
        elif lang == 'khm+eng':
            current_text["translated"] = translator.translate(extracted_text, src='km', dest='en').text
        
        # Display the original text
        text_widget.delete('1.0', tk.END)
        text_widget.insert(tk.END, current_text["original"])
        
        # Show toggle button for all modes
        toggle_button.pack(pady=5)
        separator.pack(fill='x', padx=10, pady=5)
        toggle_button.config(text="Show Translation")
        
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Create the main window
root = TkinterDnD.Tk()
root.title("Text Extractor (PDF & Image)")
root.geometry("700x600")
root.configure(bg="#121212")

# Create a label for the title
title_label = tk.Label(root, text="Text Extractor", font=("Arial", 20), fg="white", bg="#121212")
title_label.pack(pady=10)

# Create a frame for the buttons
button_frame = tk.Frame(root, bg="#121212")
button_frame.pack(pady=10)

# Create buttons to select the page segmentation mode and language
khmer_button = tk.Button(button_frame, text="Khmer", command=lambda: process_image(6, 'khm'), bg="#303030", fg="white", width=15, height=2, font=("Helvetica", 12))
khmer_button.pack(side=tk.LEFT, padx=10)

english_button = tk.Button(button_frame, text="English", command=lambda: process_image(6, 'eng'), bg="#303030", fg="white", width=15, height=2, font=("Helvetica", 12))
english_button.pack(side=tk.LEFT, padx=10)

khmer_english_button = tk.Button(button_frame, text="Khmer and English", command=lambda: process_image(6, 'khm+eng'), bg="#303030", fg="white", width=20, height=2, font=("Helvetica", 12))
khmer_english_button.pack(side=tk.LEFT, padx=10)

# Create page navigation frame
page_nav_frame = tk.Frame(root, bg="#121212")
page_nav_frame.pack_forget()

prev_button = tk.Button(page_nav_frame, text="◀ Previous", command=lambda: navigate_page(-1), 
                        bg="#303030", fg="white", width=12, font=("Helvetica", 10))
prev_button.pack(side=tk.LEFT, padx=5)

page_label = tk.Label(page_nav_frame, text="", font=("Arial", 10), fg="white", bg="#121212")
page_label.pack(side=tk.LEFT, padx=10)

next_button = tk.Button(page_nav_frame, text="Next ▶", command=lambda: navigate_page(1), 
                       bg="#303030", fg="white", width=12, font=("Helvetica", 10))
next_button.pack(side=tk.LEFT, padx=5)

# Create a text widget to display the extracted text
text_widget = tk.Text(root, wrap=tk.WORD, font=("Arial", 12), bg="#303030", fg="white", height=20)
text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Create a scrollbar for the text widget
scrollbar = tk.Scrollbar(text_widget)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_widget.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=text_widget.yview)

# Create toggle button and separator
toggle_button = tk.Button(root, text="Show Translation", command=toggle_language, 
                         bg="#303030", fg="white", width=15, height=1, font=("Helvetica", 10))
toggle_button.pack_forget()

# Create separator line
separator = tk.Frame(root, height=2, bg="#404040")
separator.pack_forget()

# Create buttons with drag and drop
for btn, txt, lng in [
    (khmer_button, "Khmer", 'khm'),
    (english_button, "English", 'eng'),
    (khmer_english_button, "Khmer and English", 'khm+eng')
]:
    btn.drop_target_register('DND_Files')
    btn.dnd_bind('<<Drop>>', lambda e, l=lng: handle_drop(e, l))
    btn.dnd_bind('<<DragEnter>>', handle_drag_enter)
    btn.dnd_bind('<<DragLeave>>', handle_drag_leave)

# Add hint label
hint_label = tk.Label(root, 
                     text="Tip: Drag and drop images or PDFs onto buttons to process",
                     font=("Arial", 9, "italic"), 
                     fg="#808080", 
                     bg="#121212")

hint_label.pack(pady=(0, 10))
# Run the Tkinter event loop
root.mainloop()
