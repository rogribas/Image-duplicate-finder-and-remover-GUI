# Image-duplicate-finder-and-remover-GUI
Made with python using imagehash and tkinter

I made this to delete duplicate photos that are the same but were resized (mostly to remove the ones sent via whatsapp that are a compress version of the original ones I took). To do this I use perceptual hashing (pHash) and join them if its hamming distance is small (they are almost identical).
It takes some time to compute if there are a lot of images on the folder selected --> O(n^2) time complexity.

UPDATE: Optimized, now it runs using multiple cores.

## Screenshot
<img src="screenshot.png" width="800">

```
python -m venv env
source env/bin/activate
pip install -r requirements.txt

python gui_duple.py
```
