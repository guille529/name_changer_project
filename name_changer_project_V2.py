import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class AnalizadorShape2DUX:

    def __init__(self, root):
        self.root = root
        self.root.title("Text Analyzer - Shape2DView")
        self.root.geometry("750x580")
        self.root.minsize(700, 520)

        # Configuración de estilo moderno
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configurar_estilos()

        self.ruta_archivo = ""
        self.contenido_original = ""
        self.encoding_detectado = "utf-8"

        # Establece el Escritorio (~/Desktop) como carpeta inicial predeterminada
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = os.path.expanduser("~")
        
        # Variable para recordar la ubicación del último archivo procesado
        self.ultimo_directorio = desktop_dir

        # Lista de capas predeterminadas
        self.capas_sugeridas = [
            "[ Custom Name ]",
            "A-ANNO",
            "A-DOOR",
            "A-EQPM",
            "A-FLOR",
            "A-GLAZ",
            "A-STRS",
            "A-WALL",
            "ELEV-ANNO",
            "ELEV-DIMS",
            "ELEV-PATT",
            "ELEV-THCK",
            "ELEV-WALL"
        ]

        # Diccionario para almacenar los widgets creados dinámicamente {nombre_original: widget_combobox}
        self.mapeo_widgets = {}

        self.crear_interfaz()

    def configurar_estilos(self):
        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure(
            "TButton", padding=6, relief="flat", background="#e1e1e1"
        )
        self.style.map(
            "TButton", background=[("active", "#d0d0d0"), ("pressed", "#bfbfbf")]
        )
        self.style.configure(
            "Accent.TButton", background="#0078d4", foreground="white"
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", "#006cc1"), ("pressed", "#005a9e")],
        )

    def crear_interfaz(self):
        # --- PANEL SUPERIOR: Unificado a un solo botón Load ---
        frame_top = ttk.Frame(self.root, padding=15)
        frame_top.pack(fill=tk.X)

        self.btn_cargar = ttk.Button(
            frame_top,
            text="⚡ Load File",
            command=self.cargar_archivo_thread,
            style="Accent.TButton",
        )
        self.btn_cargar.pack(side=tk.LEFT, padx=5)

        self.lbl_archivo = ttk.Label(
            frame_top,
            text="No file selected",
            foreground="gray",
            font=("Segoe UI", 10, "italic"),
        )
        self.lbl_archivo.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # --- BARRA DE PROGRESO (Oculta por defecto) ---
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=15, pady=(0, 5))
        self.progress.pack_forget()

        # --- PANEL CENTRAL: Contenedor con Scroll para las filas dinámicas ---
        self.frame_tabla_header = ttk.LabelFrame(
            self.root, text=" Unique Identifiers Detected ", padding=5
        )
        self.frame_tabla_header.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # Encabezados fijos simulados
        header_frame = ttk.Frame(self.frame_tabla_header)
        header_frame.pack(fill=tk.X, padx=(5, 25), pady=5)
        
        lbl_h1 = ttk.Label(header_frame, text="Original Layer name", font=("Segoe UI", 10, "bold"))
        lbl_h1.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        lbl_h2 = ttk.Label(header_frame, text="New Layer name", font=("Segoe UI", 10, "bold"))
        lbl_h2.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        # Canvas y Scrollbar para permitir el desplazamiento por la lista de combos
        self.canvas = tk.Canvas(self.frame_tabla_header, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.frame_tabla_header, orient=tk.VERTICAL, command=self.canvas.yview)
        
        # El contenedor interno donde se dibujarán las filas reales
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Asegurar que el ancho de las filas se adapte si cambia el tamaño de la ventana
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Habilitar el scroll con la rueda del ratón de forma segura
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # --- PANEL DE ACCIONES MASIVAS ---
        self.frame_masivo = ttk.Frame(self.root, padding=(15, 0, 15, 5))
        self.frame_masivo.pack(fill=tk.X)

        self.btn_reemplazar_todo = ttk.Button(
            self.frame_masivo,
            text="🔄 Replace all roots...",
            command=self.reemplazo_masivo,
            state=tk.DISABLED,
        )
        self.btn_reemplazar_todo.pack(side=tk.LEFT, padx=5)

        # --- PANEL INFERIOR: Boton de Guardado ---
        frame_bot = ttk.Frame(self.root, padding=15)
        frame_bot.pack(fill=tk.X)

        self.btn_guardar = ttk.Button(
            frame_bot,
            text="💾 Save Changes...",
            command=self.guardar_cambios_menu,
            state=tk.DISABLED,
            style="Accent.TButton",
        )
        self.btn_guardar.pack(side=tk.RIGHT, padx=5)

    def on_mousewheel(self, event):
        focused_widget = self.root.focus_get()
        if focused_widget and "combobox" in str(focused_widget).lower():
            return "break"
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def cargar_archivo_thread(self):
        ruta = filedialog.askopenfilename(
            initialdir=self.ultimo_directorio,
            title="Open File",
            filetypes=[
                ("Compatible Files", "*.dxf *.txt *.json *.xml *.log"),
                ("All Files", "*.*"),
            ],
        )
        if not ruta:
            return

        self.ruta_archivo = ruta
        self.ultimo_directorio = os.path.dirname(ruta)

        self.btn_cargar.config(state=tk.DISABLED)
        self.progress.pack(fill=tk.X, padx=15, pady=(0, 5))
        self.progress.start(10)

        threading.Thread(
            target=self.procesar_carga_archivo, args=(ruta,), daemon=True
        ).start()

    def procesar_carga_archivo(self, ruta):
        contenido = None
        encodings = ["utf-8", "latin-1", "cp1252"]

        for enc in encodings:
            try:
                with open(ruta, "r", encoding=enc) as f:
                    contenido = f.read()
                self.encoding_detectado = enc
                break
            except UnicodeDecodeError:
                continue

        self.root.after(
            0, lambda: self.finalizar_carga_interfaz(ruta, contenido)
        )

    def finalizar_carga_interfaz(self, ruta, contenido):
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_cargar.config(state=tk.NORMAL)

        if contenido is None:
            messagebox.showerror("Read Error", "Could not decode the file.")
            return

        self.contenido_original = contenido
        self.lbl_archivo.config(
            text=os.path.basename(ruta),
            foreground="black",
            font=("Segoe UI", 10, "bold"),
        )

        patron = r"\b\w*Shape2DView\w*\b"
        encontrados = set(re.findall(patron, self.contenido_original))

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.mapeo_widgets.clear()

        if encontrados:
            self.scrollable_frame.columnconfigure(0, weight=1)
            self.scrollable_frame.columnconfigure(1, weight=1)

            for idx, item in enumerate(sorted(list(encontrados))):
                lbl_original = ttk.Label(self.scrollable_frame, text=item, padding=5, anchor="w")
                lbl_original.grid(row=idx, column=0, sticky="ew", padx=5, pady=2)

                combo = ttk.Combobox(self.scrollable_frame, values=self.capas_sugeridas, state="readonly")
                combo.set(item if item in self.capas_sugeridas else self.capas_sugeridas[0])
                combo.grid(row=idx, column=1, sticky="ew", padx=5, pady=2)

                combo.unbind_class("TCombobox", "<MouseWheel>")

                self.mapeo_widgets[item] = combo
                combo.bind("<<ComboboxSelected>>", lambda e, orig=item, cb=combo: self.verificar_seleccion_custom(orig, cb))

            self.btn_guardar.config(state=tk.NORMAL)
            self.btn_reemplazar_todo.config(state=tk.NORMAL)
        else:
            self.btn_guardar.config(state=tk.DISABLED)
            self.btn_reemplazar_todo.config(state=tk.DISABLED)
            messagebox.showinfo(
                "Analysis Finished", "No matches containing 'Shape2DView' were found here."
            )

    def verificar_seleccion_custom(self, original, combo_widget):
        if combo_widget.get() == "[ Custom Name ]":
            self.solicitar_nombre_custom(original, combo_widget)

    def solicitar_nombre_custom(self, original, combo_widget):
        ventana_custom = tk.Toplevel(self.root)
        ventana_custom.title("Custom Name")
        ventana_custom.geometry("380x120")
        ventana_custom.resizable(False, False)
        ventana_custom.transient(self.root)
        ventana_custom.grab_set()

        ttk.Label(ventana_custom, text=f"Enter custom name for '{original}':").pack(
            anchor=tk.W, padx=15, pady=(10, 5)
        )
        entry_custom = ttk.Entry(ventana_custom, width=45)
        entry_custom.pack(padx=15, fill=tk.X)
        entry_custom.focus_set()

        def confirmar(event=None):  # Acepta un argumento 'event' opcional para cuando se presiona Enter
            nuevo_texto = entry_custom.get().strip()
            if nuevo_texto:
                valores_actuales = list(combo_widget['values'])
                if nuevo_texto not in valores_actuales:
                    valores_actuales.append(nuevo_texto)
                    combo_widget['values'] = valores_actuales
                
                combo_widget.set(nuevo_texto)
                ventana_custom.destroy()
            else:
                messagebox.showwarning("Warning", "The field cannot be empty.")

        # --- ¡SOLUCIÓN AQUÍ! Vincular la tecla Enter (<Return>) para confirmar ---
        entry_custom.bind("<Return>", confirmar)

        ttk.Button(ventana_custom, text="Apply", command=confirmar).pack(
            side=tk.RIGHT, padx=15, pady=10
        )

    def reemplazo_masivo(self):
        ventana_masiva = tk.Toplevel(self.root)
        ventana_masiva.title("Bulk Root Replacement")
        ventana_masiva.geometry("450x140")
        ventana_masiva.resizable(False, False)
        ventana_masiva.transient(self.root)
        ventana_masiva.grab_set()

        ttk.Label(
            ventana_masiva,
            text="Replace the base word 'Shape2DView' in ALL visible dropdowns with:",
            wraplength=400,
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        entry_raiz = ttk.Entry(ventana_masiva, width=50)
        entry_raiz.insert(0, "NewView")
        entry_raiz.pack(padx=15, fill=tk.X)
        entry_raiz.focus_set()

        def ejecutar_cambio_masivo(event=None):  # Acepta un argumento 'event' opcional para Enter
            nueva_raiz = entry_raiz.get().strip()
            if not nueva_raiz:
                return

            for original, combo in self.mapeo_widgets.items():
                nuevo_valor = original.replace("Shape2DView", nueva_raiz)
                
                valores = list(combo['values'])
                if nuevo_valor not in valores:
                    valores.append(nuevo_valor)
                    combo['values'] = valores
                combo.set(nuevo_valor)

            ventana_masiva.destroy()
            messagebox.showinfo(
                "Success", "All dropdown inputs have been modified in the table layout."
            )

        # Vincular Enter también en la ventana masiva para agilizar el uso
        entry_raiz.bind("<Return>", ejecutar_cambio_masivo)

        ttk.Button(
            ventana_masiva, text="Change All", command=ejecutar_cambio_masivo
        ).pack(side=tk.RIGHT, padx=15, pady=10)

    def guardar_cambios_menu(self):
        ruta_archivo_actual = self.ruta_archivo

        mapeo_cambios = {}
        for original, combo in self.mapeo_widgets.items():
            valor_seleccionado = combo.get()
            if valor_seleccionado != original and valor_seleccionado != "[ Custom Name ]":
                mapeo_cambios[original] = valor_seleccionado

        if not mapeo_cambios:
            messagebox.showinfo(
                "No Changes", "No modifications were captured from the dropdown list."
            )
            return

        decision = messagebox.askyesnocancel(
            "Save Changes",
            "How would you like to save the changes?\n\n"
            "🟢 [Yes] = Overwrite file (Automatically creates a .bak backup)\n"
            "🔵 [No] = Save as a new file\n"
            "🔴 [Cancel] = Go back",
        )

        if decision is None:
            return

        ruta_destino = ruta_archivo_actual

        if decision is False:  # Save as...
            nombre_base, ext = os.path.splitext(ruta_archivo_actual)
            ruta_destino = filedialog.asksaveasfilename(
                initialdir=self.ultimo_directorio,
                title="Save New File",
                defaultextension=ext,
                filetypes=[("Same Type Files", f"*{ext}"), ("All Files", "*.*")],
                initialfile=os.path.basename(nombre_base) + "_modified" + ext,
            )
            if not ruta_destino:
                return
            self.ultimo_directorio = os.path.dirname(ruta_destino)
        else:  # Sobrescribir con respaldo preventivo
            try:
                import shutil

                shutil.copy2(ruta_archivo_actual, ruta_archivo_actual + ".bak")
            except Exception as e:
                messagebox.showwarning(
                    "Backup Warning",
                    f"Could not create the backup .bak file, proceeding to save anyway: {e}",
                )

        # Aplicar los reemplazos en el documento
        contenido_final = self.contenido_original
        for original, nuevo in mapeo_cambios.items():
            patron_reemplazo = r"\b" + re.escape(original) + r"\b"
            contenido_final = re.sub(patron_reemplazo, nuevo, contenido_final)

        try:
            with open(ruta_destino, "w", encoding=self.encoding_detectado) as f:
                f.write(contenido_final)

            messagebox.showinfo(
                "Success!",
                f"Process completed successfully.\nDestination: {os.path.basename(ruta_destino)}",
            )
            
            self.contenido_original = contenido_final
            self.ruta_archivo = ruta_destino
            
            nuevos_elementos = set(mapeo_cambios.values())
            for original in self.mapeo_widgets.keys():
                if original not in mapeo_cambios:
                    nuevos_elementos.add(original)
                    
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.mapeo_widgets.clear()
            
            for idx, item in enumerate(sorted(list(nuevos_elementos))):
                lbl_original = ttk.Label(self.scrollable_frame, text=item, padding=5, anchor="w")
                lbl_original.grid(row=idx, column=0, sticky="ew", padx=5, pady=2)
                combo = ttk.Combobox(self.scrollable_frame, values=self.capas_sugeridas, state="readonly")
                combo.set(item if item in self.capas_sugeridas else self.capas_sugeridas[0])
                combo.grid(row=idx, column=1, sticky="ew", padx=5, pady=2)
                
                combo.unbind_class("TCombobox", "<MouseWheel>")
                
                self.mapeo_widgets[item] = combo
                combo.bind("<<ComboboxSelected>>", lambda e, orig=item, cb=combo: self.verificar_seleccion_custom(orig, cb))

        except Exception as e:
            messagebox.showerror("Write Error", f"Could not save the file:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AnalizadorShape2DUX(root)
    root.mainloop()