Bicleaner Hardrules 2.9.1:
* Fix hardrules crash without metadata.

Bicleaner Hardrules 2.9.0:
* Accept HF identifiers in `--metadata` argument.

Bicleaner Hardrules 2.8.1:
* Fix `no_url` regex
* Fix builds with pip >= 23 using `fasttext-wheel`.

Bicleaner Hardrules 2.8.0:
* Update KenLM installation instructions
* Update FastSpell to 0.8
    * Dictionaries installed as a dependency.
    * Better coverage for Icelandic.

Bicleaner Hardrules 2.7.0:
* Relax unicode noise rule for Icelandic and Finish.

Bicleaner Hardrules 2.6.0:
* Update FastSpell to 0.5: some improvements for Slovene and Serbo-Croatian language detection.

Bicleaner Hardrules 2.5.1:
* Fix installation instructions.
* Freeze some dependencies.

Bicleaner Hardrules 2.5:
* Disable `no_urls` by default.

Bicleaner Hardrules 2.4:
* Update FastSpell
* Fix FastSpell imports.
* Improved `no_paren` rule.
* Extended `no_escaped_unicode` rule.
* More aggressive url filtering.

Bicleaner Hardrules 2.3:
* Automated KenLM build.
* Check lenght ratio with characters in non-CJK.

Bicleaner Hardrules 2.2:
* Refinement of minimum length and repeated words for CJK.
* Filter sentences with inconsistencies in numbers (disabled by default)
* Filter sentences with characters in differents scripts/writing systems (disabled by default)

Bicleaner Hard-rules 2.0:
* Parametrized hardrules: now each rule can be enabled or disabled via YAML config file.
* Run all mode: run all rules instead of stopping in the first discard.
* New hardrule: discard sentences that contain repeated words
* Avoid downloading multiple fasttext models in parallel on first run.

Bicleaner Hard-rules 1.3.1:
* Fix PyPi release.

Bicleaner Hard-rules 1.3:
* Filter bad encoding issues with Ã and Â
* Change identical rules with a single identical without non-alpha
* Return exit code 1 when a process encounters an error.
* Tag as wrong the sentence pairs with an empty side.
* Language identifier is now FastSpell
* Tag as wrong the sentence pairs with wrong number of columns.

Bicleaner Hard-rules 1.2:
* Add `--score_only` mode.

Bicleaner Hard-rules 1.1:
* Separate `wrong_tu` code.
* Load `lm` only when necessary.

Bicleaner Hard-rules 1.0:
* Split Hardrules into a separate package.

Bicleaner 0.14: 
* Bicleaner hardrules changes:
  * New rule: filter out sentences containing gluedWordsLikeThis.
  * Rule change: Relaxed c\_different\_language rule for similar languages.
  * New rule: filter out porn sentences using FastText classifier.
  * Parameters changed: `-s/--source_lang` and `-t/--target_lang` are no longer mandatory (if a metadata .yaml file is provided)
* Other
   * Now using [sacremoses](https://github.com/alvations/sacremoses) instead of [mosestokenizer](https://github.com/luismsgomes/mosestokenizer)

Bicleaner 0.13:
* Bicleaner hardrules changes:
  * Rule change: Relaxed c\_minimal\_length to accept 3-word sentences	
  * New feature: LM filtering (moved from Bicleaner Classify)
  * New parameter: `--disable_lm_filter`, `--metadata` and `--lm_threshold`, to support LM filtering
* Other:
  * Updated requirements

Bicleaner 0.12:
* Bicleaner hardrules changes:
  * New rule: c\_identical\_wo\_punct to reject sentences only different in punctuation (and it's case insensitive)
  * New rule:  Sentences containing "Re:" are rejected
  * Rule change: c\_minimal\_length now rejects sentences with both sides <= 3 words (instead of only one)
  * Rule change: c\_identical and c\_identical\_wo\_digits now is case insensitive
  * Rule change: Breadcrumbs rule now split into c\_no\_breadcrumbs1 and c\_no\_breadcrumbs2
  * Rule change: Breadcrumbs2 now includes character "·" in the rejected characters
  * Rule change: c\_length now compares byte length ratio (will avoid rejecting valid sentences due to length ratio when comparing languages with different alphabets)
  * Changed behaviour for `--annotated_output` argument in hardrules. See README.md for more information.
  * New parameter: `--disable_lang_ident` flag to avoid applying rules that need to identify the language
