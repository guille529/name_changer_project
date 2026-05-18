import os
import re
import threading
import json  # Para los configs externos
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class AnalizadorShape2DUX:

    def __init__(self, root):
        self.root = root
        self.root.title("Text Analyzer - Shape2DView")
        self.root.geometry("750x640")
        self.root.minsize(700, 580)

        # Look and feel de la app
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configurar_estilos()

        self.ruta_archivo = ""
        self.contenido_original = ""
        self.encoding_detectado = "utf-8"

        # Tiramos al escritorio por defecto si existe
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = os.path.expanduser("~")
        
        self.ultimo_directorio = desktop_dir

        # Opciones base de la lista desplegable
        self.capas_sugeridas = [
            "[ Custom Name ]", "A-ANNO", "A-DOOR", "A-EQPM", "A-FLOR", 
            "A-GLAZ", "A-STRS", "A-WALL", "ELEV-ANNO", "ELEV-DIMS", 
            "ELEV-PATT", "ELEV-THCK", "ELEV-WALL"
        ]

        # Aca guardamos los combobox de la pantalla
        self.mapeo_widgets = {}
        
        # Diccionario para acordarnos de que correspondencia iba con cada nombre original
        self.mapeo_config_cargada = {}

        self.crear_interfaz()

    def cargar_configuracion_desde_archivo(self):
        """ Selector para levantar un json con las traducciones guardadas """
        ruta_config = filedialog.askopenfilename(
            initialdir=self.ultimo_directorio,
            title="Select Configuration File",
            filetypes=[("Configuration Files", "*.json"), ("All Files", "*.*")]
        )
        if not ruta_config:
            return

        try:
            with open(ruta_config, "r", encoding="utf-8") as f:
                datos = json.load(f)
                
            # Validamos que venga con la estructura que esperamos
            if isinstance(datos, dict) and "mapeo_capas" in datos:
                self.mapeo_config_cargada = datos["mapeo_capas"]
                
                # Si viene con extras en la lista, los metemos tambien
                if "lista_sugeridas" in datos:
                    self.capas_sugeridas = datos["lista_sugeridas"]
            else:
                messagebox.showerror("Error", "The selected JSON file does not have a valid configuration structure.")
                return

            # Si ya hay cosas cargadas en pantalla, metemos los nombres guardados de una
            if self.mapeo_widgets:
                for original, combo in self.mapeo_widgets.items():
                    # Refrescamos las opciones de la lista por si acaso
                    combo['values'] = self.capas_sugeridas
                    
                    # Si habiamos guardado algo para esta fila, se lo clavamos directamente
                    if original in self.mapeo_config_cargada:
                        valor_guardado = self.mapeo_config_cargada[original]
                        
                        # Si no esta en la lista, lo agregamos al vuelo para evitar que explote
                        valores_actuales = list(combo['values'])
                        if valor_guardado not in valores_actuales:
                            valores_actuales.append(valor_guardado)
                            combo['values'] = valores_actuales
                        
                        combo.set(valor_guardado)
                    else:
                        # Si no tiene traduccion, dejamos lo que habia o la primera opcion
                        combo.set(original if original in self.capas_sugeridas else self.capas_sugeridas[0])
                        
            messagebox.showinfo("Success", "Configuration loaded. Saved names have been auto-applied.")
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not read the configuration file:\n{e}")

    def guardar_configuracion_en_archivo(self):
        """ Guarda la foto actual de lo que pusiste en pantalla """
        ruta_destino = filedialog.asksaveasfilename(
            initialdir=self.ultimo_directorio,
            title="Save Configuration As...",
            defaultextension=".json",
            filetypes=[("Configuration Files", "*.json"), ("All Files", "*.*")],
            initialfile="my_translations_config.json"
        )
        if not ruta_destino:
            return

        # Armamos el mapa con lo que esta seleccionado ahora mismo en los desplegables
        mapa_a_guardar = {}
        for original, combo in self.mapeo_widgets.items():
            valor_seleccionado = combo.get()
            # Pasamos del 'Custom Name' generico, nos interesan los nombres reales
            if valor_seleccionado != "[ Custom Name ]":
                mapa_a_guardar[original] = valor_seleccionado

        # Empaquetamos todo para el JSON
        datos_config = {
            "mapeo_capas": mapa_a_guardar,
            "lista_sugeridas": self.capas_sugeridas
        }

        try:
            with open(ruta_destino, "w", encoding="utf-8") as f:
                json.dump(datos_config, f, indent=4, ensure_ascii=False)
                
            # Seteamos la memoria local por si sigue usando la app sin cerrarla
            self.mapeo_config_cargada = mapa_a_guardar
            messagebox.showinfo("Success", f"Configuration successfully saved to:\n{os.path.basename(ruta_destino)}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save the configuration file:\n{e}")

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
        # Arriba: Cargar archivo de texto
        frame_top = ttk.Frame(self.root, padding=15)
        frame_top.pack(fill=tk.X)

        self.btn_cargar = ttk.Button(
            frame_top,
            text="Load File",
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

        # Loader de carga
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=15, pady=(0, 5))
        self.progress.pack_forget()

        # Centro: Contenedor con scroll para los nombres encontrados
        self.frame_tabla_header = ttk.LabelFrame(
            self.root, text=" Unique Identifiers Detected ", padding=5
        )
        self.frame_tabla_header.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        header_frame = ttk.Frame(self.frame_tabla_header)
        header_frame.pack(fill=tk.X, padx=(5, 25), pady=5)
        
        lbl_h1 = ttk.Label(header_frame, text="Original Layer name", font=("Segoe UI", 10, "bold"))
        lbl_h1.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        lbl_h2 = ttk.Label(header_frame, text="New Layer name", font=("Segoe UI", 10, "bold"))
        lbl_h2.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.canvas = tk.Canvas(self.frame_tabla_header, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.frame_tabla_header, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Medio: Seccion para manejar los configs externos
        frame_config_btns = ttk.LabelFrame(self.root, text=" Configuration Management ", padding=10)
        frame_config_btns.pack(fill=tk.X, padx=15, pady=5)

        self.btn_load_conf = ttk.Button(
            frame_config_btns,
            text="Load Configuration From File...",
            command=self.cargar_configuracion_desde_archivo
        )
        self.btn_load_conf.pack(side=tk.LEFT, padx=5)

        self.btn_save_conf = ttk.Button(
            frame_config_btns,
            text="Save Configuration As...",
            command=self.guardar_configuracion_en_archivo
        )
        self.btn_save_conf.pack(side=tk.LEFT, padx=5)

        # Abajo: Guardar el archivo modificado
        frame_bot = ttk.Frame(self.root, padding=15)
        frame_bot.pack(fill=tk.X)

        self.btn_guardar = ttk.Button(
            frame_bot,
            text="Save Changes to File...",
            command=self.guardar_cambios_menu,
            state=tk.DISABLED,
            style="Accent.TButton",
        )
        self.btn_guardar.pack(side=tk.RIGHT, padx=5)

    def on_mousewheel(self, event):
        # Bloqueamos el scroll del canvas si el foco esta arriba de un combobox abierto
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

        # Lo mandamos a un hilo para que no se congele la ventana si el archivo pesa mucho
        threading.Thread(
            target=self.procesar_carga_archivo, args=(ruta,), daemon=True
        ).start()

    def procesar_carga_archivo(self, ruta):
        contenido = None
        encodings = ["utf-8", "latin-1", "cp1252"]

        # Probamos encodings tipicos hasta que alguno ande
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

        # Buscamos coincidencias con regex
        patron = r"\b\w*Shape2DView\w*\b"
        encontrados = set(re.findall(patron, self.contenido_original))

        # Limpiamos lo que habia antes
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
                
                # Auto-seleccionamos el valor guardado de la config si existe coincidencia
                if item in self.mapeo_config_cargada:
                    valor_mapeado = self.mapeo_config_cargada[item]
                    valores_combo = list(combo['values'])
                    if valor_mapeado not in valores_combo:
                        valores_combo.append(valor_mapeado)
                        combo['values'] = valores_combo
                    combo.set(valor_mapeado)
                else:
                    combo.set(item if item in self.capas_sugeridas else self.capas_sugeridas[0])

                combo.grid(row=idx, column=1, sticky="ew", padx=5, pady=2)
                combo.unbind_class("TCombobox", "<MouseWheel>")

                self.mapeo_widgets[item] = combo
                combo.bind("<<ComboboxSelected>>", lambda e, orig=item, cb=combo: self.verificar_seleccion_custom(orig, cb))

            self.btn_guardar.config(state=tk.NORMAL)
        else:
            self.btn_guardar.config(state=tk.DISABLED)
            messagebox.showinfo(
                "Analysis Finished", "No matches containing 'Shape2DView' were found here."
            )

    def verificar_seleccion_custom(self, original, combo_widget):
        if combo_widget.get() == "[ Custom Name ]":
            self.solicitar_nombre_custom(original, combo_widget)

    def solicitar_nombre_custom(self, original, combo_widget):
        # Mini popup flotante para escribir a mano
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

        def confirmar(event=None):
            nuevo_texto = entry_custom.get().strip()
            if nuevo_texto:
                valores_actuales = list(combo_widget['values'])
                if nuevo_texto not in valores_actuales:
                    valores_actuales.append(nuevo_texto)
                    combo_widget['values'] = valores_actuales
                    
                    if nuevo_texto not in self.capas_sugeridas:
                        self.capas_sugeridas.append(nuevo_texto)
                
                combo_widget.set(nuevo_texto)
                ventana_custom.destroy()
            else:
                messagebox.showwarning("Warning", "The field cannot be empty.")

        entry_custom.bind("<Return>", confirmar)

        ttk.Button(ventana_custom, text="Apply", command=confirmar).pack(
            side=tk.RIGHT, padx=15, pady=10
        )

    def guardar_cambios_menu(self):
        ruta_archivo_actual = self.ruta_archivo

        # Filtramos solo lo que cambio de verdad
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
            "Yes = Overwrite file (Automatically creates a .bak backup)\n"
            "No = Save as a new file\n"
            "Cancel = Go back",
        )

        if decision is None:
            return

        ruta_destino = ruta_archivo_actual

        if decision is False:
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
        else:
            # Metemos un backup rapido por si las moscas
            try:
                import shutil
                shutil.copy2(ruta_archivo_actual, ruta_archivo_actual + ".bak")
            except Exception as e:
                messagebox.showwarning(
                    "Backup Warning",
                    f"Could not create the backup .bak file, proceeding to save anyway: {e}",
                )

        # Procesamos el archivo aplicando el cambiazo de los nombres usando regex exacto
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
            
            # Seteamos el estado actual con el archivo guardado por si quiere seguir editando
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
                
                if item in self.mapeo_config_cargada:
                    combo.set(self.mapeo_config_cargada[item])
                else:
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