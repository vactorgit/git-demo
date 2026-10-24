# YouTube Transcript

Paste a YouTube link, get the full transcript. Works with watch links, youtu.be links, Shorts, embeds, live links and bare video IDs.

- Timestamps on or off (click a timestamp to jump the video there)
- Switch between caption languages the video has
- Copy to clipboard or download as .txt

## Quickest way: the script

```
pip install youtube-transcript-api
python get_transcript.py
```

Paste a link when it asks. The transcript prints on screen and saves as `transcript-VIDEO_ID.txt`. Add `--timestamps` for timestamped lines:

```
python get_transcript.py https://youtu.be/VIDEO_ID --timestamps
```

## Run the web page version

```
cd transcript
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5001.

## Limits

- It only works on videos that have captions (manual or auto-generated). It doesn't transcribe audio itself.
- YouTube blocks most cloud server IPs (AWS, Google Cloud, Render, etc.) from fetching captions. It works fine run from your own computer. To host it publicly you'd need a residential proxy; `youtube-transcript-api` supports one through its `proxy_config` option.
