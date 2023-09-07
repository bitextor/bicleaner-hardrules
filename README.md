
# bicleaner-hardrules

![License](https://img.shields.io/badge/License-GPLv3-blue.svg)


Bicleaner hard-rules (`bicleaner-hardrules`) is a pre-filtering step for obvious noise based on rules, poor language based on general language modelling and vulgar language based on specific language modelling.
It is part of [Bicleaner](https://github.com/bitextor/bicleaner).


## Installation & Requirements
Bicleaner hard-rules is written in Python and can be installed using `pip`.
It also requires the [KenLM](https://github.com/kpu/kenlm) Python bindings with support for 7-gram language models.
You can easily install it by running the following command:

```bash
pip install bicleaner-hardrules
pip install --config-settings="--build-option=--max_order=7" https://github.com/kpu/kenlm/archive/master.zip
```

Since v1.3 hard-rules uses [FastSpell](https://github.com/mbanon/fastspell) that requires `python-dev` and `libhunspell-dev`:
```bash
sudo apt install python-dev libhunspell-dev
```

Hunspell dictionaries used by default are automatically installed.
If you need to change default configuration for language identification, see https://github.com/mbanon/fastspell#configuration.

After installation, a binary file (`bicleaner-hardrules`) will be located in your `python/installation/prefix/bin` directory. This is usually `$HOME/.local/bin` or `/usr/local/bin/`.


### Installing from source
When installing from source, either directly from the cloned repository
```
git clone https://github.com/bitextor/bicleaner-hardrules
cd bicleaner-hardrules
pip install .
```
or from `pip`
```
pip install bicleaner-hardrules --no-binary :all:
```

## Cleaning

`bicleaner-hardrules` aims at detecting obvious noisy sentence pairs in a parallel corpus.
Sentences that are considered noisy will be tagged with a `0` and the rest will be tagged with a `1`.

By default, the input file (the parallel corpus to be classified) must contain at least two columns, being:

* col1: Source sentence
* col2: Target sentence

but the source and target sentences column index can be customized by using the `--scol` and `--tcol` flags, in case you have more columns.

The generated output file will contain the same lines and columns that the original input file had, adding an extra column containing the Bicleaner hard-rules tag.

This tool can be run with

```bash
bicleaner-hardrules [-h]
                    [--annotated_output]
                    -s SOURCE_LANG
                    -t TARGET_LANG
                    [--tmp_dir TMP_DIR]
                    [-b BLOCK_SIZE]
                    [-p PROCESSES]
                    [--run_all_rules]
                    [--disable_lang_ident]
                    [--disable_minimal_length]
                    [--scol SCOL]
                    [--tcol TCOL]
                    [--disable_lm_filter]
                    [--disable_porn_removal]
                    [--dont_ignore_long]
                    [--metadata METADATA]
                    [--lm_threshold LM_THRESHOLD]
                    [-q]
                    [--debug]
                    [--logfile LOGFILE]
                    [input]
                    [output]
```

### Parameters

* positional arguments:
  * `input`: Tab-separated files to be classified (default line format: `SOURCE_SENTENCE TARGET_SENTENCE [EXTRA_COLUMNS]`, tab-separated). When input is -, reads standard input.
  * `output`: Output of the classification (default: standard output). When output is -, writes standard output.
* Optional:
  * `--annotated_output`: Adds an extra column with each sentence's evaluation ("keep" if the sentence is good, otherwise the reason for rejecting (default: False)
  * `--metadata METADATA`: Training metadata (YAML file), generated by `bicleaner-train` or [downloaded](https://github.com/bitextor/bicleaner-data/releases/latest) as a part of a language pack. You just need to `untar` the language pack for the pair of languages that you want to clean. The tar file contains the YAML metadata file.
  There's a script that can download and unpack available language packs. As an example, if you are planning to clean an English to Czeck file, use:
  ```bash
  $ bicleaner-download en cs ./models
  ```
  to download the English-Czech language pack to the ./models directory and unpack it. You can also use `bilceaner-ai-download` for Bicleaner AI models and provide HF identifier to the `--metadata` argument in case it was downloaded from there like:
  ```
  bicleaner-hardrules --metadata "bitextor/bicleaner-ai-full-en-es" ...
  ```
  For further details, see [here](https://github.com/bitextor/bicleaner-ai#download-a-model).
  * `-S SOURCE_TOKENIZER_COMMAND`: Source language tokenizer full command (including flags if needed). If not given, Sacremoses tokenizer is used (with `escape=False` option).
  * `-T TARGET_TOKENIZER_COMMAND`: Target language tokenizer full command (including flags if needed). If not given, Sacremoses tokenizer is used (with `escape=False` option).
  * `--scol SCOL`: Source sentence column (starting in 1) (default: 3)
  * `--tcol TCOL`: Target sentence column (starting in 1) (default: 4)
  * `--tmp_dir TMP_DIR`: Temporary directory where creating the temporary files of this program (default: default system temp dir, defined by the environment variable TMPDIR in Unix)
  * `-b BLOCK_SIZE, --block_size BLOCK_SIZE`: Sentence pairs per block (default: 10000)
  * `-p PROCESSES, --processes PROCESSES`: Number of processes to use (default: all CPUs minus one)
  * `--lm_threshold LM_THRESHOLD`: Threshold for language model fluency scoring. All sentence pairs whose LM fluency score falls below the threshold are removed (classifier score set to 0), unless the option --keep_lm_result is set. (default: 0.5)
  * `-A` or `--run_all_rules`: Run all rules for each sentence instead of stopping at first discard (default: False)
  * `-c CONFIG.yml` or `--config CONFIG.yml`: Rules configuration file (default: None)
  * `--disable_hardrules`: Disables the bicleaner_hardrules filtering (only bicleaner_classify is applied) (default: False)
  * `--disable_lm_filter`: Disables LM filtering.
  * `--disable_porn_removal`: Disables porn removal.
  * `--disable_minimal_length`: Don't apply minimal length rule (default: False).
  * `--dont_ignore_long`: Don't ingore sentences that are longer than 10000 characters (default: False).
  * `-h, --help`: show this help message and exit

* Logging:
  * `-q, --quiet`: Silent logging mode (default: False)
  * `--debug`: Debug logging mode (default: False)
  * `--logfile LOGFILE`: Store log to a file (default: `stderr`)
  * `-v, --version`: show version of this script and exit

### Example

```bash
bicleaner-hardrules  \
        corpus.en-es.raw  \
        corpus.en-es.classifed
```

This will read the "`corpus.en-es.raw`" file, tag it and write the resul in `corpus.classified`.
Each line of the new file will contain the same content as the input file, adding a column with the tag given by the Bicleaner hard-rules.

### Automatic test

We included a small test corpus and a script to check that your Bicleaner classifier is working as expected. 
In order to use it, just run:

```bash
python3.7 -m pytest -s tests/hardrules_test.py
```

This will download the required language pack, classify the provided test corpus, and check the resulting classification scores. If everything went as expected, the output will be "1 passed in XX.XX seconds". All downloaded data will be removed at the end of the testing session.

## Understanding annotated output

When using the `--annotated_output` flag, an extra column with each sentence's evaluation is added to the output.  If the evalution is `keep`, it means that the sentence is good and passed all filters. Any other value in the extra column means that the sentence should be rejected, indicating the reason why. See  below the list of posible rejecting values and their meanings:

```
no_empty	Sentence is empty
not_too_long	Sentence is more than 1024 characters long
not_too_short	Sentence is less than	3 words long
length_ratio	The length ratio between the source sentence and target sentence (in bytes) is too low or too high
no_identical	Alphabetic content in source sentence and target sentence is identical
no_literals  Unwanted literals: "Re:","{{", "%s", "}}", "+++", "***", '=\"'
no_only_symbols	The ratio of non-alphabetic characters in source sentence is more than 90%
no_only_numbers	The ratio of numeric characters in source sentence is too high
no_urls	There are URLs (disabled by default)
no_breadcrumbs	There are more than 2 breadcrumb characters in the sentence
no_glued_words	There are words in the sentence containing too many uppercased characters between lowercased characters
no_repeated_words There are more than 1 consecutive words repeated
no_unicode_noise	Too many characters from unwanted unicode in source sentence
no_space_noise	Too many consecutive single characters separated by spaces in the sentence (excludes digits)
no_paren	Too many parenthesis or brackets in sentence
no_escaped_unicode	There is unescaped unicode characters in sentence
no_bad_encoding	Source sentence or target sentence contains mojibake
no_titles	All words in source sentence or target sentence are uppercased or in titlecase
no_wrong_language	Sentence is not in the desired language
no_porn	Source sentence or target sentence contains text identified as porn
no_number_inconsistencies	Sentence contains different numbers in source and target (disabled by default)
no_script_inconsistencies	Sentence source or target contains characters from different script/writing systems (disabled by default)
lm_filter	The sentence pair has low fluency score from the language model
```

## Training classifiers

In case you need to train a new classifier (i.e. because it is not available in the language packs provided at [bicleaner-data](https://github.com/bitextor/bicleaner-data/releases/latest)), you can use `bicleaner-train` .
`bicleaner-train` is a Python3 tool that allows you to train a classifier which predicts 
whether a pair of sentences are mutual translations or not and discards too noisy sentence pairs. Visit our [Wiki](https://github.com/bitextor/bicleaner/wiki/How-to-train-your-Bicleaner) for a detailed example on Bicleaner training.

## Citation

If you find Bicleaner useful, please consider citing the following papers:

> V. M. Sánchez-Cartagena, M. Bañón, S. Ortiz-Rojas and G. Ramírez-Sánchez,\
> "[Prompsit's submission to WMT 2018 Parallel Corpus Filtering shared task](http://www.statmt.org/wmt18/pdf/WMT116.pdf)",\
>in *Proceedings of the Third Conference on Machine Translation, Volume 2: Shared Task Papers*.\
>Brussels, Belgium: Association for Computational Linguistics, October 2018

```latex
@InProceedings{prompsit:2018:WMT,
  author    = { V\'{i}ctor M. S\'{a}nchez-Cartagena and Marta Ba{\~n}\'{o}n and Sergio Ortiz-Rojas and Gema Ram\'{i}rez-S\'{a}nchez},
  title     = {Prompsit's submission to WMT 2018 Parallel Corpus Filtering shared task},
  booktitle = {Proceedings of the Third Conference on Machine Translation, Volume 2: Shared Task Papers},
  month     = {October},
  address   = {Brussels, Belgium},
  publisher = {Association for Computational Linguistics}
}
```


> Gema Ramírez-Sánchez, Jaume Zaragoza-Bernabeu, Marta Bañón and Sergio Ortiz Rojas \
> "[Bifixer and Bicleaner: two open-source tools to clean your parallel data.](https://eamt2020.inesc-id.pt/proceedings-eamt2020.pdf#page=311)",\
>in *Proceedings of the 22nd Annual Conference of the European Association for Machine Translation*.\
>Lisboa, Portugal: European Association for Machine Translation, November 2020

```latex
@InProceedings{prompsit:2020:EAMT,
  author    = {Gema Ram\'{i}rez-S\'{a}nchez and Jaume Zaragoza-Bernabeu and Marta Ba{\~n}\'{o}n and Sergio Ortiz-Rojas},
  title     = {Bifixer and Bicleaner: two open-source tools to clean your parallel data.},
  booktitle = {Proceedings of the 22nd Annual Conference of the European Association for Machine Translation},
  pages	    = {291--298},
  isbn      = {978-989-33-0589-8},
  year	    = {2020},
  month     = {November},
  address   = {Lisboa, Portugal},
  publisher = {European Association for Machine Translation}
}
```

## Making a PyPi Release
In the root dir of the repo, run:
```bash
./scripts/release.sh
```
This script will create source distribution, compile binary distribution and convert wheel file to generic python3.
Then it will upload them to PyPi, you need a user account maintainer of `bicleaner-hardrules` in PyPi and user token.

___

![Connecting Europe Facility](https://www.paracrawl.eu/images/logo_en_cef273x39.png)

All documents and software contained in this repository reflect only the authors' view. The Innovation and Networks Executive Agency of the European Union is not responsible for any use that may be made of the information it contains.
