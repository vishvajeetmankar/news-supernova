# Music folder

YouTube doesn't give a public download API for its Audio Library, so this one
step needs a **5-minute manual one-time job**:

1. Go to https://studio.youtube.com -> left menu -> **Audio Library**
2. Filter by mood/genre you like for news shorts (e.g. "Upbeat", "Dramatic", "Cinematic")
3. Pick 10-15 tracks marked **"no attribution required"** (safest) and click the
   download icon next to each
4. Drop the downloaded `.mp3` files directly into this `music/` folder
5. Commit + push to your repo

That's it — `main.py` will automatically pick a random track and a random
5-second slice from it every time it runs, so your shorts won't feel repetitive.

If a track requires attribution (YouTube will tell you), just add a line
crediting it in your video descriptions — `main.py`'s description field can
be edited to include this if needed.
