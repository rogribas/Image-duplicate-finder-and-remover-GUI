import argparse
import math
import os
import queue
import threading
import time
from tkinter import *
from tkinter import filedialog
from tkinter import messagebox
from tkinter.ttk import Progressbar

from PIL import Image, ImageTk
import imagehash

from concurrent.futures import ProcessPoolExecutor


def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

class Photo(object):

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.size = os.path.getsize(path)
        self.size_text = convert_size(os.path.getsize(path))
        self.delete = False
        self.hash_value = None
        self.distance = None

    def __lt__(self, other):
        return self.name.split('.')[0] < other.name.split('.')[0]


def hashfunc_parallel(photo):
    try:
        photo.hash_value = imagehash.phash(Image.open(photo.path), hash_size=64,
                                    highfreq_factor=4)
        return photo
    except Exception as e:
        print('Problem:', e, 'with', photo.name)

class SimilarImagesFinder(object):

    def find_similar_images(self, folder_path, outqueue=None,
                            hashfunc=imagehash.phash):

        def is_image(filename):
            f = filename.lower()
            return f.endswith(".png") or f.endswith(".jpg") or \
                f.endswith(".jpeg") or f.endswith(".bmp") or f.endswith(".gif") or '.jpg' in f

        TIME_0 = time.perf_counter()
        TIME = time.perf_counter()

        photos_list = []
        for path in os.listdir(folder_path):
            if is_image(path):
                photos_list.append(Photo(os.path.join(folder_path, path)))

        photos_hash_dict = {}
        total_photos = len(photos_list) * 2
        count = 0
        for photo in sorted(photos_list):
            try:
                photo.hash_value = hashfunc(Image.open(photo.path), hash_size=64,
                                            highfreq_factor=4)
            except Exception as e:
                print('Problem:', e, 'with', photo.name)
                continue
            # print(photo.path)
            if photo.hash_value in photos_hash_dict:
                photos_hash_dict[photo.hash_value].append(photo)
            else:
                photos_hash_dict[photo.hash_value] = [photo]

            count += 1
            if outqueue:
                outqueue.put(count/total_photos)

        print('HASHING ENDED')
        hash_time = time.perf_counter() - TIME
        print('hash time', hash_time)
        TIME = time.perf_counter()

        merged_hashes = set()
        results_duplicated = {}

        for hash_j in list(photos_hash_dict):
            count += 1
            if outqueue:
                outqueue.put(count/total_photos)
            # print('HASH', hash_j)
            for hash_k, photos_k in photos_hash_dict.items():
                dist = hash_k - hash_j
                if dist < 500 and hash_k not in merged_hashes:
                    merged_hashes.add(hash_k)
                    hash_j_str = str(hash_j)[:32]
                    if hash_j_str in results_duplicated:
                        results_duplicated[hash_j_str] += photos_k
                    else:
                        results_duplicated[hash_j_str] = photos_k

        print('DISTANCE ENDED')
        dist_time = time.perf_counter() - TIME
        print('distance time', dist_time)

        num_photos_to_delete = 0
        for hash_k in list(results_duplicated):
            if len(results_duplicated[hash_k]) < 2:
                del results_duplicated[hash_k]
            else:
                results_duplicated[hash_k] = sorted(results_duplicated[hash_k], key=lambda x: x.size, reverse=True)
                for i, photo_obj in enumerate(results_duplicated[hash_k]):
                    if i == 0:
                        photo_obj.delete = False
                    else:
                        photo_obj.delete = True
                        num_photos_to_delete += 1

        if outqueue:
            outqueue.put([num_photos_to_delete, results_duplicated])

        t_time = time.perf_counter() - TIME_0
        print('total time', t_time)


class GUIDuple(object):

    PHOTO_SAVE_COLOR = '#70d067'
    PHOTO_DELETE_COLOR = '#e3464e'
    COLOR_FRAMES1 = '#ececec'
    COLOR_FRAMES2 = '#999'
    COLOR_FRAMES3 = '#ccc'

    def __init__(self):
        self.results = {}
        self.num_photos_to_delete = 0

        self.root = Tk()
        self.root.title('Duplicates finder')
        w, h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+0+0" % (w, h))

        # create all of the main containers
        self.frame_header1 = Frame(self.root, padx=15, pady=5, bg=self.COLOR_FRAMES1)
        self.frame_header2 = Frame(self.root, padx=15, pady=5, bg=self.COLOR_FRAMES1)
        self.frame_center = Frame(self.root)
        self.frame_bottom = Frame(self.root, padx=15, pady=15, bg=self.COLOR_FRAMES1)

        # layout all of the main containers
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.frame_header1.grid(row=0, sticky="ew")
        self.frame_header2.grid(row=1, sticky="ew")
        self.frame_center.grid(row=2, sticky="nsew")
        self.frame_bottom.grid(row=3, sticky="ew")

        # widgets frame_header1
        self.frame_header1.grid_columnconfigure(1, weight=1)
        self.label_title = Label(self.frame_header1, text='DUPLICATES FINDER', font="-weight bold", bg=self.COLOR_FRAMES1)
        self.label_title.grid(row=0, column=0)
        self.folder_path = StringVar()
        self.label_folder = Entry(self.frame_header1, state='disabled', width=40, textvariable=self.folder_path, highlightbackground=self.COLOR_FRAMES1)
        self.label_folder.grid(row=0, column=2)
        self.btn_browse_folder = Button(self.frame_header1, text="Choose folder", command=self.action_browse, highlightbackground=self.COLOR_FRAMES1)
        self.btn_browse_folder.grid(row=0, column=3, padx=(5, 50))
        self.btn_scan = Button(self.frame_header1, text="Scan", command=self.action_scan, state='disabled', highlightbackground=self.COLOR_FRAMES1)
        self.btn_scan.grid(row=0, column=4)

        # widgets frame_header1
        self.prgs_bar = Progressbar(self.frame_header2)
        self.prgs_bar.grid(row=0, column=0)
        self.prgs_bar.pack(expand=True, fill='both')

        # widgets frame_bottom
        self.frame_bottom.grid_columnconfigure(2, weight=1)
        self.label_delete_num = Label(self.frame_bottom, text='0', bg=self.COLOR_FRAMES1)
        self.label_delete_num.grid(row=0, column=0)
        self.label_delete_str = Label(self.frame_bottom, text='photos to delete', bg=self.COLOR_FRAMES1)
        self.label_delete_str.grid(row=0, column=1)
        self.btn_delete_photos = Button(self.frame_bottom, text="Delete photos", state=DISABLED, command=self.action_delete, highlightbackground=self.COLOR_FRAMES1)
        self.btn_delete_photos.grid(row=0, column=3)

        # frames frame_center
        self.frame_center.grid_columnconfigure(1, weight=1)
        self.frame_center.grid_rowconfigure(0, weight=1)
        self.frame_center1 = Frame(self.frame_center, bg=self.COLOR_FRAMES2, padx=15, pady=5)
        self.frame_center1.grid(row=0, column=0)
        self.frame_center1.grid(row=0, sticky="nsew")
        self.frame_center2 = Frame(self.frame_center, pady=15, bg=self.COLOR_FRAMES3)
        self.frame_center2.grid(row=0, column=1)
        self.frame_center2.grid(row=0, sticky="nsew")

        # widgets frame_center1
        self.frame_center1.grid_rowconfigure(1, weight=1)
        self.label_list = Label(self.frame_center1, text="Duplicates", bg=self.COLOR_FRAMES2)
        self.label_list.grid(row=0, column=0)
        self.lb_ids = []
        self.lb = Listbox(self.frame_center1, font=("Courier", 12), height=600)
        self.lb.grid(row=1, column=0)
        self.lb.bind('<<ListboxSelect>>', self.onselect)
        self.lb.bind('1', self.toggle_photo_key)
        self.lb.bind('2', self.toggle_photo_key)
        self.lb.bind('3', self.toggle_photo_key)
        self.lb.bind('4', self.toggle_photo_key)
        self.lb.bind('5', self.toggle_photo_key)
        self.lb.bind('6', self.toggle_photo_key)
        self.lb.bind('7', self.toggle_photo_key)
        self.lb.bind('8', self.toggle_photo_key)
        self.lb.bind('9', self.toggle_photo_key)

        self.labels_memory = []
        self.labels_img_memory = []

    def toggle_photo_key(self, evt):
        position = int(evt.keysym) - 1
        self.toggle_photo(position)

    def toggle_photo(self, position):
        # Update object photo
        photo_obj = self.results[self.lb_ids[self.lb.curselection()[0]]][position]
        photo_obj.delete = not photo_obj.delete
        # Update label photo
        if photo_obj.delete:
            bg_color = self.PHOTO_DELETE_COLOR
            self.update_num_photos_to_delete(self.num_photos_to_delete + 1)
        else:
            bg_color = self.PHOTO_SAVE_COLOR
            self.update_num_photos_to_delete(self.num_photos_to_delete - 1)
        self.labels_memory[position][0].config(bg=bg_color)

    def update_num_photos_to_delete(self, num):
        self.num_photos_to_delete = num
        if self.num_photos_to_delete < 1:
            self.btn_delete_photos.config(state='disabled')
        else:
            self.btn_delete_photos.config(state='normal')
        self.label_delete_num.config(text=str(self.num_photos_to_delete))

    def update(self, outqueue):
        try:
            msg = outqueue.get_nowait()
            if isinstance(msg, list):
                print('SCAN FINISHED')
                self.update_num_photos_to_delete(msg[0])
                self.results = msg[1]
                for i, r in self.results.items():
                    self.lb_ids.append(i)
                    self.lb.insert(END, str(i)[:8] + ' (%d)' % len(r))
                self.btn_browse_folder.config(state='normal')
                self.btn_scan.config(state='normal')
                self.btn_delete_photos.config(state='normal')
                self.prgs_bar['value'] = 0

                if self.results:
                    self.lb.select_set(0)
                    self.lb.event_generate('<<ListboxSelect>>')
                    self.lb.focus_set()
                else:
                    messagebox.showinfo("Duplicate finder", "No duplicates found!")

            else:
                self.prgs_bar['value'] = msg * 100
                self.root.after(100, self.update, outqueue)
        except queue.Empty:
            self.root.after(100, self.update, outqueue)

    def action_browse(self):
        # Allow user to select a directory and store it in global var
        # called folder_path
        filename = filedialog.askdirectory()
        self.folder_path.set(filename)
        if filename:
            self.btn_scan.config(state='normal')
        print(filename)

    def clear_photos(self):
        for labels_obj in self.labels_memory:
            for label in labels_obj:
                label.destroy()

    def action_scan(self):
        self.btn_browse_folder.config(state='disabled')
        self.btn_scan.config(state='disabled')
        self.lb.delete(0,'end')
        self.clear_photos()
        self.outqueue = queue.Queue()
        thr = threading.Thread(target=SimilarImagesFinder().find_similar_images,
                               args=(self.folder_path.get(), self.outqueue))
        thr.start()
        self.root.after(250, self.update, self.outqueue)

    def img_click(self, evt):
        position = int(evt.widget.grid_info()["column"])
        self.toggle_photo(position)

    def onselect(self, evt):
        w = evt.widget
        index = int(w.curselection()[0])
        value = w.get(index)
        # delete old labels
        self.clear_photos()
        self.labels_memory = []
        self.labels_img_memory = []
        # calculate widths
        frame_width = self.frame_center2.winfo_width()
        grid_width = frame_width/len(self.results[self.lb_ids[index]])
        photo_with = grid_width - 40

        count = 0
        for photo in self.results[self.lb_ids[index]]:
            self.frame_center2.grid_columnconfigure(count, minsize=grid_width)

            img = Image.open(photo.path)
            img.thumbnail((photo_with, photo_with))
            render = ImageTk.PhotoImage(img)
            self.labels_img_memory.append(render)
            photo_border_color = self.PHOTO_DELETE_COLOR if photo.delete else self.PHOTO_SAVE_COLOR
            label_img = Label(self.frame_center2, image=self.labels_img_memory[count], borderwidth=10, bg=photo_border_color)
            label_img.grid(row=4, column=count)
            label_img.bind("<Button-1>", self.img_click)

            label_text = Label(self.frame_center2, anchor=N, font="TkDefaultFont 20 bold", text=photo.size_text)
            label_text.grid(row=5, column=count)
            label_text2 = Label(self.frame_center2, anchor=N, text=photo.name)
            label_text2.grid(row=6, column=count)

            self.labels_memory += [[label_img, label_text, label_text2]]
            count += 1

    def action_delete(self):
        result = messagebox.askquestion("Delete",
                    "Are You Sure you want to delete %d photos?" % self.num_photos_to_delete, icon='warning')
        if result == 'yes':
            for _, photos in self.results.items():
                for photo_obj in photos:
                    if photo_obj.delete:
                        os.remove(photo_obj.path)
            self.results = {}
            self.update_num_photos_to_delete(0)
            self.lb.delete(0,'end')
            self.clear_photos()

    def run(self):
        mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', type=str)
    args = parser.parse_args()
    if args.debug:
        SimilarImagesFinder().find_similar_images(args.debug)
    else:
        guiduple = GUIDuple()
        guiduple.run()
