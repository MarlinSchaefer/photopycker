import tkinter as tk
from tkinter.filedialog import askdirectory
from tkinter import ttk
from PIL import Image, ImageTk
import os
import shutil
import threading
from argparse import ArgumentParser


class CopyFilesProgress(tk.Toplevel):
    def __init__(self, parent, source, dest, img_names, do_export, *args,
                 **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.source = source
        self.dest = dest
        self.img_names = img_names
        self.do_export = do_export
        self.cancel = 0
        
        self.title('Copying Files')
        self.build()
        self.attributes('-topmost', 'true')
        self.start()
    
    def build(self):
        self.plen = self.calculate_length()
        self.pvar = tk.IntVar(self, 0)
        self.progbar = ttk.Progressbar(self, orient=tk.HORIZONTAL,
                                       maximum=self.plen, variable=self.pvar,
                                       mode='determinate')
        self.progbar.pack()
        
        cancel_btn = tk.Button(self, text='Cancel', command=self.cancel_press)
        cancel_btn.pack()
    
    def cancel_press(self):
        self.cancel = 1
    
    def calculate_length(self):
        total = 0
        for fn, export in self.do_export.items():
            if not export:
                continue
            total += os.path.getsize(os.path.join(self.source, fn))
        return total
    
    def start(self):
        self.total = 0
        self.thread = threading.Thread(target=self.copy_files)
        self.lock = threading.Lock()
        self.status = 0
        self.update_bar()
    
    def update_bar(self):
        if self.status == 0:
            self.thread.start()
            self.status = 1
            self.update_bar()
        elif self.status == 1:
            with self.lock:
                self.pvar.set(self.total)
            if self.cancel == 2:
                self.status = -1
            if self.pvar.get() >= self.plen:
                self.status = 2
            self.after(100, self.update_bar)
        elif self.status == 2:
            self.thread.join()
            self.destroy()
        elif self.status == -1:
            self.thread.kill()
            self.destroy()
    
    def copy_files(self):
        for sfn, dfn in self.img_names.items():
            with self.lock:
                if self.cancel == 1:
                    self.cancel = 2
                    return
            if self.do_export[sfn]:
                src = os.path.join(self.source, sfn)
                dst = os.path.join(self.dest, dfn + os.path.splitext(sfn)[1])
                shutil.copy2(src, dst)
                with self.lock:
                    self.total += os.path.getsize(src)
        return


class NameClashWindow(tk.Toplevel):
    def __init__(self, parent, filename, name, img_names, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.filename = filename
        self.name = name
        self.img_names = img_names
        self.ret = None
        self.title('Duplicate Name')
        self.build()
        self.attributes('-topmost', 'true')
        self.grab_set()
    
    def generate_unique(self, name):
        idx = 1
        new_name = f'{name}({idx})'
        while new_name in self.img_names.values():
            idx += 1
            new_name = f'{name}({idx})'
        return new_name
    
    def build(self):
        self.lbl = tk.Label(self, text=f'Another image is named {self.name}.')
        
        self.buttons = tk.Frame(self)
        self.cancel_btn = tk.Button(self.buttons, text='Cancel',
                                    command=self.cancel_press)
        self.rename_btn = tk.Button(self.buttons, text='Rename',
                                    command=self.rename_press)
        self.cancel_btn.grid(row=0, column=0)
        self.rename_btn.grid(row=0, column=1)
        
        self.rename = tk.Frame(self)
        self.rename_lbl = tk.Label(self.rename, text='New name:')
        self.res = tk.StringVar()
        self.res.trace("w", self.check_name)
        self.rename_ent = tk.Entry(self.rename, textvariable=self.res)
        self.rename_ent.insert(0, self.generate_unique(self.name))
        self.rename_lbl.grid(row=0, column=0)
        self.rename_ent.grid(row=0, column=1)
                
        self.lbl.grid(row=0, column=0)
        self.rename.grid(row=1, column=0)
        self.buttons.grid(row=2, column=0)
        
        self.rename_ent.focus()
        self.rename_ent.icursor(tk.END)
        
        self.bind('<Return>', self.return_press)
        self.bind('<Escape>', self.cancel_press)
    
    def return_press(self, event=None):
        if self.rename_btn['state'] != tk.DISABLED:
            self.rename_press()
    
    def cancel_press(self, event=None):
        self.ret = None
        self.finalize()
        
    def rename_press(self, event=None):
        name = self.rename_ent.get()
        print(name)
        if name == '':
            self.cancel_press()
            return
        self.ret = True
        self.img_names[self.filename] = name
        self.finalize()
    
    def finalize(self):
        self.grab_release()
        self.destroy()
    
    def check_name(self, *args):
        name = self.res.get()
        if name in self.img_names.values():
            if self.rename_btn['state'] != tk.DISABLED:
                self.rename_ent.configure(background='red')
                self.rename_btn['state'] = tk.DISABLED
        else:
            if self.rename_btn['state'] != tk.NORMAL:
                self.rename_ent.configure(background='white')
                self.rename_btn['state'] = tk.NORMAL
    
    def show(self):
        self.wm_deiconify()
        self.grab_set()
        self.wait_window()
        return self.ret


class App(tk.Tk):
    def __init__(self, directory, *args, preload=True, cache=True, maxsize=720,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.title('ImagePycker')
        self.extensions = ['.jpeg', '.jpg', '.JPG', '.png']
        self.directory = directory
        self.files = [fn for fn in os.listdir(self.directory)
                      if os.path.splitext(fn)[1] in self.extensions]
        self.imgs = {}
        self.maxsize = maxsize
        if preload:
            for fn in self.files:
                
                path = os.path.join(self.directory, fn)
                img = self.load_image(path)
                self.imgs[fn] = img
        self.cache = cache
        self.img_names = {fn: os.path.splitext(fn)[0] for fn in self.files}
        self.changed = {fn: False for fn in self.files}
        self.do_export = {fn: True for fn in self.files}
        self.build()
    
    def build(self):
        self.grid_columnconfigure(0, weight=1)
        # Build top bar
        self.topbar = tk.Frame(self)
        self.larrow = tk.Button(self.topbar, text='<', command=self.prev_img)
        self.rarrow = tk.Button(self.topbar, text='>', command=self.next_img)
        self.indicator = tk.Frame(self.topbar)
        vcmd = (self.register(self.validate_num),
                '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        self.current = tk.Entry(self.indicator, validate='key',
                                validatecommand=vcmd)
        self.current.insert(tk.END, '1')
        self.max_count = tk.Label(self.indicator, text=f' / {len(self.files)}')
        
        self.current.grid(row=0, column=0)
        self.max_count.grid(row=0, column=1)
        
        self.larrow.grid(row=0, column=0)
        self.indicator.grid(row=0, column=1)
        self.rarrow.grid(row=0, column=2)
        
        self.topbar.grid(row=0, column=0)
        
        # Build image viewer
        img = self.get_img(self.files[0])
        self.img_viewer = tk.Label(self, image=img)
        self.img_viewer.image = img
        self.idx = 0
        self.img_viewer.grid(row=1, column=0)
        
        # Build rename
        self.botbar = tk.Frame(self)
        left = tk.Frame(self.botbar)
        right = tk.Frame(self.botbar)
        self.img_name = tk.StringVar()
        self.img_name.set(self.files[0])
        self.img_label = tk.Label(right, textvariable=self.img_name)
        self.img_rename = tk.Entry(right)
        self.img_rename.insert(tk.END, self.img_names[self.files[0]])
        self.export_var = tk.IntVar(self, int(True))
        self.export_ckb = tk.Checkbutton(left, text='',
                                         variable=self.export_var,
                                         command=self.export_ckb_press)
        lbl = tk.Label(left, text='Keep image: ')
        
        self.botbar.grid_columnconfigure(0, weight=1)
        self.botbar.grid_columnconfigure(1, weight=1)
        left.grid(row=0, column=0, sticky='W')
        right.grid(row=0, column=1, sticky='E')
        lbl.grid(row=0, column=0)
        self.export_ckb.grid(row=0, column=1)
        self.img_label.grid(row=0, column=0)
        self.img_rename.grid(row=0, column=1)
        self.botbar.grid(row=2, column=0, sticky='NSWE')
        
        # Export and apply buttons
        self.export_row = tk.Frame(self)
        self.export_btn = tk.Button(self.export_row, text='Export',
                                    command=self.export)
        self.hide_var = tk.IntVar(self, int(False))
        self.hide_ckb = tk.Checkbutton(self.export_row, text='Hide renamed',
                                       variable=self.hide_var)
        
        self.export_btn.grid(row=0, column=0)
        self.hide_ckb.grid(row=0, column=1)
        self.export_row.grid(row=3, column=0)
        
        # Setup bindings
        self.bind('<Left>', self.left_arrow_press)
        self.bind('<Right>', self.right_arrow_press)
        self.bind('<Up>', self.export_arrow_press)
        self.bind('<Down>', self.no_export_arrow_press)
        self.img_rename.bind('<FocusIn>', self.rename_focus)
        self.current.bind('<Return>', self.change_idx_entry)
        self.current.bind('<FocusIn>', self.current_focus)
        
        # Set focus
        self.img_rename.focus()
    
    def export_ckb_press(self, event=None):
        fn = self.files[self.idx]
        self.do_export[fn] = not self.do_export[fn]
        self.export_var.set(int(self.do_export[fn]))
    
    def export_arrow_press(self, event=None):
        fn = self.files[self.idx]
        self.do_export[fn] = True
        self.export_var.set(int(self.do_export[fn]))
    
    def no_export_arrow_press(self, event=None):
        fn = self.files[self.idx]
        self.do_export[fn] = False
        self.export_var.set(int(self.do_export[fn]))
    
    def current_focus(self, event=None):
        self.current.selection_range(0, tk.END)
    
    def change_idx_entry(self, event=None):
        sidx = self.current.get()
        if sidx == '':
            idx = self.idx
        else:
            idx = int(sidx) - 1
        self.change_img(idx)
    
    def rename_focus(self, event=None):
        fn = self.files[self.idx]
        if self.changed[fn]:
            self.img_rename.icursor(tk.END)
        else:
            self.img_rename.selection_range(0, tk.END)
    
    def left_arrow_press(self, event=None):
        self.prev_img()
    
    def right_arrow_press(self, event=None):
        self.next_img()
    
    def get_img(self, filename):
        if filename in self.imgs:
            img = self.imgs[filename]
        else:
            path = os.path.join(self.directory, filename)
            img = self.load_image(path)
            if self.cache:
                self.imgs[filename] = img
        return ImageTk.PhotoImage(img)
    
    def prev_img(self):
        hide = bool(self.hide_var.get())
        if hide:
            idx = self.idx - 1
            while self.changed[self.files[idx % len(self.files)]]:
                idx -= 1
        else:
            idx = self.idx - 1
        self.change_img(idx)
        return
    
    def next_img(self):
        hide = bool(self.hide_var.get())
        if hide:
            idx = self.idx + 1
            while self.changed[self.files[idx % len(self.files)]]:
                idx += 1
        else:
            idx = self.idx + 1
        self.change_img(idx)
        return
    
    def change_img(self, idx):
        name = self.img_rename.get()
        if name in self.img_names.values() and name != self.img_names[self.files[self.idx]]:
            changed = NameClashWindow(self, self.files[self.idx], name,
                                      self.img_names).show()
            if changed is not None:
                self.changed[self.files[self.idx]] = True
        else:
            if name != os.path.splitext(self.files[self.idx])[0]:
                self.img_names[self.files[self.idx]] = name
                self.changed[self.files[self.idx]] = True
        
        idx = idx % len(self.files)
        self.idx = idx
        self.current.delete(0, tk.END)
        self.current.insert(0, str(idx + 1))
        img = self.get_img(self.files[idx])
        self.img_viewer.configure(image=img)
        self.img_viewer.image = img
        
        self.img_name.set(self.files[idx])
        self.img_rename.delete(0, tk.END)
        self.img_rename.insert(0, self.img_names[self.files[idx]])
        
        self.export_var.set(int(self.do_export[self.files[self.idx]]))
        
        self.img_rename.focus()
        self.rename_focus()
        return
    
    def validate_num(self, d, i, P, s, S, v, V, W):
        if not (P.isdigit() or P == ''):
            return False
        if P == '':
            return True
        return 0 < int(P) < len(self.files) + 1
    
    def export(self):
        target = askdirectory(parent=self, title='Export Directory',
                              initialdir=self.directory)
        if target is None:
            return
        CopyFilesProgress(self, self.directory, target, self.img_names,
                          self.do_export)
    
    def apply_rename(self):
        return
    
    def load_image(self, path):
        temp = Image.open(path)
        img = temp.copy()
        temp.close()
        if self.maxsize is not None:
            img.thumbnail((self.maxsize, self.maxsize))
        return img


def main():
    parser = ArgumentParser()
    
    parser.add_argument('directory', type=str, default=os.getcwd(), nargs='?',
                        help='The directory to open.')
    parser.add_argument('--preload', action='store_true',
                        help='Preload all images in the directory into '
                             'memory.')
    parser.add_argument('--maxsize', type=int, default=720,
                        help='Size of the smaller side of the image when '
                             'shown.')
    
    args = parser.parse_args()
    
    app = App(args.directory, preload=args.preload, maxsize=args.maxsize)
    app.mainloop()


if __name__ == '__main__':
    main()
