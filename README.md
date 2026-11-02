
<img src="www/vwwizard_logo.png" width="400"/>

Interactive application for visualizing whole-brain surface vertex-wise statistical maps.
The app generates **3D brain surface maps** based on a given results directory. 
The results directory should contain the output generated using [`verywise`](https://seredef.github.io/verywise/index.html) (or `QDECR`).

You can try the application online [here](https://seredef-verywise-wizard.share.connect.posit.cloud/).

### Running the application locally 
The 3D brain surface reconstructions (especially the high-resolution ones) may be faster to generate on your local machine. 
To run the application locally, clone the repository and then follow either option below.
The app needs Python 3.11 or 3.12.
```
git clone https://github.com/SereDef/verywise-wizard
cd verywise-wizard
```

<details open>
<summary><b>Using <code>uv</code> (recommended)</b></summary>

[`uv`](https://docs.astral.sh/uv/) installs the right Python version and all dependencies for you:
```
uv sync

uv run shiny run --launch-browser app.py
```
</details>

<details>
<summary><b>Using <code>pip</code></b></summary>

`requirements.txt` is generated from `pyproject.toml`, so it pins the same versions:
```
pip install -r requirements.txt

shiny run --launch-browser app.py
```
</details>

> After changing a dependency in `pyproject.toml`, regenerate `requirements.txt` with
> `uv export --no-hashes --no-dev --no-emit-project -o requirements.txt`
> (the deployed app reads that file).

## Funders  
<img src="www/funders.png" height="100" alt="Funders"/>

This work was supported by the *FLAG-ERA* grant [**Infant2Adult**](https://www.infant2adult.com/home) and by The Netherlands Organization for Health Research and Development (ZonMw, grant number 16080606). 

