import sys
import logging
import regex
import re
import os
import sys

from unicodedata import category as cat
from fastspell import FastSpell
from collections import OrderedDict
from inspect import getmembers, signature
from copy import deepcopy

try:
    from .lm import load_lm_filter
    from .tokenizer import Tokenizer
    from .writing_scripts import script_family
except (SystemError, ImportError):
    from lm import load_lm_filter
    from tokenizer import Tokenizer
    from writing_scripts import script_family

tbl_non_alpha = [chr(i) for i in range(sys.maxunicode) if not cat(chr(i)).startswith('L')]
tbl_non_alpha = str.maketrans('', '', ''.join(tbl_non_alpha))
regex_blank = regex.compile("[ \u00A0]")
regex_alpha = regex.compile("[[:alpha:]]")
regex_numbers = regex.compile("[[:digit:]]")
#regex_url = regex.compile('((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]|\((:?[^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
regex_url = regex.compile("(http(s)?:\/\/.)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)")
#regex_breadcrumbs = regex.compile("([ ][-/»][ ]|[|<>→←]|[ ][:][:][ ])")
regex_breadcrumbs1 = regex.compile("([ ][-/][ ]|[<>*]|[ ][:][ ])")
regex_breadcrumbs2 = regex.compile("([ ][»][ ]|[|→←•·¬])")
regex_unicode_noise = regex.compile("[\x80-\xFF]{3,}")
regex_unicode_noise_relaxed = regex.compile("[\x80-\xFF]{7,}")
regex_spaces_noise = regex.compile("([ ]\D){4,}[ ]")
#regex_paren = regex.compile("[][(){}]")
regex_paren = r"\[|\]|\(|\)|{|}|⟨|⟩"
regex_unwanted = regex.compile("[+*]")
regex_inconditional = regex.compile("=\"")
regex_escaped_unicode = regex.compile("[\\\\][xu][0-9a-fA-F]{2,}") #matches stuff like \\u245 and \\xc3
#regex_glued_words = regex.compile("\b[[:alpha:]]*[[:lower:]][[:upper:]][[:alpha:]]*)
regex_glued_words = regex.compile("([[:alpha:]]*[[:upper:]]{1}[[:lower:]]+){3}")
regex_repeated_words = regex.compile(r"\b(.+)\1\b")
regex_repeated_without_words = regex.compile(r"(.+)\1")

safe_noise_detection_langs = {"en", "es", "fr", "pl", "de", "it", "pt", "nl", "cs", "ro", "fi", "lv", "et", "bg", "hr", "da", "hu", "ga", "eu", "gl", "sl", "sv", "mt", "sk", "is", "lt", "nb", "nn", "no"}

#similar_pairs = [{"es","ca"}, {"es","gl"}, {"pt","gl"}, {"no","nn"}, {"no", "da"}]
atilde_langs = {"pt"}
acumflex_langs = {"cy", "fr", "fa", "it", "pt", "tr", "vi",}
CJK = {"zh", "ja", "ko"}

class Hardrules():
    # Define default settings
    # the order of execution will be the order of the dict
    rule_pipeline = OrderedDict()
    rule_pipeline['no_empty'] = True
    rule_pipeline['not_too_long'] = 1024
    rule_pipeline['not_too_short'] = 3
    rule_pipeline['length_ratio'] = 2.0
    rule_pipeline['no_identical'] = True
    rule_pipeline['no_literals'] = ["Re:","{{", "%s", "}}", "+++", "***", '=\"']
    rule_pipeline['no_only_symbols'] = True
    rule_pipeline['no_only_numbers'] = True
    rule_pipeline['no_urls'] = False
    rule_pipeline['no_breadcrumbs'] = True
    rule_pipeline['no_glued_words'] = True
    rule_pipeline['no_repeated_words'] = True
    rule_pipeline['no_unicode_noise'] = True
    rule_pipeline['no_space_noise'] = True
    rule_pipeline['no_paren'] = True
    rule_pipeline['no_escaped_unicode'] = True
    rule_pipeline['no_bad_encoding'] = True
    rule_pipeline['no_titles'] = True
    rule_pipeline['no_number_inconsistencies'] = False
    rule_pipeline['no_script_inconsistencies'] = False
    rule_pipeline['no_wrong_language'] = True
    rule_pipeline['no_porn'] = True
    rule_pipeline['lm_filter'] = True
    
    def __init__(self, args):
        # Load LM
        if not args.disable_lm_filter:
            self.lm_filter = load_lm_filter(args.source_lang,
                    args.target_lang, args.metadata_yaml,
                    args.source_tokenizer_command, args.target_tokenizer_command)
        else:
            self.lm_filter = None
        self.lm_threshold = args.lm_threshold

        # Load porn removal
        if not args.disable_porn_removal:
            try:
                self.porn_removal_side = args.metadata_yaml['porn_removal_side']
                self.porn_removal = args.porn_removal
                if self.porn_removal_side == 'tl':
                    self.porn_tokenizer = Tokenizer(args.target_tokenizer_command, args.target_lang)
                else:
                    self.porn_tokenizer = Tokenizer(args.source_tokenizer_command, args.source_lang)                
            except KeyError:
                self.porn_removal = None
                self.porn_tokenizer = None
                self.porn_removal_side = None
                    
        else:
            self.porn_removal = None
            self.porn_tokenizer = None
            self.porn_removal_side = None

        # Load FastSpell
        if not args.disable_lang_ident:
            self.fastspell_src = FastSpell(args.source_lang, mode="aggr")
            self.fastspell_trg = FastSpell(args.target_lang, mode="aggr")
        else:
            self.fastspell_src = None
            self.fastspell_trg = None

        self.src_lang = args.source_lang
        self.trg_lang = args.target_lang
        self.run_all_rules = args.run_all_rules
        self.disable_minimal_length = args.disable_minimal_length
        self.rules = {n: f for n, f in getmembers(self) if n.startswith('c_')}
        logging.debug(f"Available rules: {self.rules.keys()}")

        # Create dict with with config
        self.config = deepcopy(self.rule_pipeline)
        if args.rules_config is not None:
            # Validate config
            dif = args.rules_config.keys() - self.rule_pipeline.keys()
            if dif:
                raise Exception(f"Unkown options in config: {dif}")

            # Overwrite with user-defined options
            for name, param in args.rules_config.items():
                self.config[name] = param

        logging.debug(f"Enabled rules: {self.config.keys()}")

        # Check that all the rule functions are implemented
        for rule_name in self.config.keys():
            if 'c_' + rule_name not in self.rules:
                raise NotImplementedError(f"Rule {rule_name} is not implemented")

    def wrong_tu(self, left, right):
        # Create list of discard tags
        # for each rule that triggers discard
        # append rule name
        if self.run_all_rules:
            discards = []

        logging.debug(f"{left}\t{right}")

        # Loop over rule pipeline
        for rule_name in self.config.keys():
            if not self.config[rule_name]:
                continue

            # Obtain function to be applied
            rule_func = self.rules['c_' + rule_name]

            # Determine if rule has to be applied to both sides separated, or together
            #TODO is reflection slow?
            if 'sentence' in signature(rule_func).parameters:
                # Iterate over left and right side
                for sidename, side in {'left': left, 'right': right}.items():
                    keep = rule_func(side, sidename)
                    logging.debug(f"Rule '{rule_name}({sidename})': {not keep}")
                    if not keep and self.run_all_rules:
                        # Especial case for empty rule to avoid crashes in other rules
                        if rule_name == 'no_empty':
                            #check if both are empty:
                            if left=="":
                                discards.append("no_empty(left)")
                            if right=="":
                                discards.append("no_empty(right)")
                            return discards
                        else:   
                            discards.append(f"{rule_name}({sidename})")                            
                    elif not keep:
                        return f"{rule_name}({sidename})"
            else:
                # Apply rule to both sides
                keep = rule_func(left, right)
                logging.debug(f"Rule '{rule_name}(left,right)': {not keep}")
                if not keep and self.run_all_rules:
                    discards.append(f"{rule_name}(left,right)")
                elif not keep:
                    return f"{rule_name}(left,right)"

        if self.run_all_rules and discards:
            return discards
        else:
            return False

    def c_no_empty(self, sentence, side):
        return sentence != ""

    def c_no_titles(self, left, right):    
        return not ((len(left.strip().split(" ")) > 1 and left.istitle()) and (len(right.strip().split(" ")) > 1 and right.istitle()))

    def c_not_too_long(self, sentence, side):
        return len(sentence) < self.config['not_too_long']

    def c_not_too_short(self, sentence, side):
        lang = self.src_lang
        if side == "right":
            lang = self.trg_lang

        if self.disable_minimal_length:
            return True

        # for Chinese, Japanese and Korean characters rather than words are used
        if lang in CJK:
            return len(sentence) >= self.config['not_too_short']

        """ Counts number of whitespace, requires >= 2 (3 words) """
        return len(regex_blank.findall(sentence)) >= self.config['not_too_short']-1

    def c_no_identical(self, left, right):
        left = left.translate(tbl_non_alpha)
        right = right.translate(tbl_non_alpha)
        return left.casefold() != right.casefold()

    def c_length_ratio(self, left, right):
        lower_ratio = 1/self.config["length_ratio"]
        upper_ratio = self.config["length_ratio"]
        if self.src_lang in CJK or self.trg_lang in CJK:
            return lower_ratio <= len(left.encode("utf8"))/len(right.encode("utf8")) <= upper_ratio
        else:
            return lower_ratio <= len(left)/len(right) <= upper_ratio

    def c_no_wrong_language(self, sentence, side='left'):
        if self.fastspell_src is None:
            return True

        if side == 'left':
            lang = self.src_lang
            fastspell = self.fastspell_src
        else:
            lang = self.trg_lang
            fastspell = self.fastspell_trg

        return fastspell.getlang(sentence) == lang

    def c_lm_filter(self, left, right):
        if self.lm_filter is None:
            return True
        return self.lm_filter.score(left, right) >= self.lm_threshold

    def c_no_bad_encoding(self, sentence, side):
        lang = self.src_lang if side == 'left' else self.trg_lang

        if lang not in atilde_langs and 'Ã' in sentence:
            return False
        if lang not in acumflex_langs and 'Â' in sentence:
            return False
        return True

    def c_no_only_symbols(self, sentence, side):
        return len(regex_alpha.findall(sentence)) / len(sentence) > 0.1

    def c_no_only_numbers(self, sentence, side):
        lang = self.src_lang if side == 'left' else self.trg_lang
        threshold = 0.5
        if lang in CJK:
            threshold = 0.7
        return len(regex_numbers.findall(sentence)) / len(sentence) < threshold

    def c_no_urls(self, sentence, side):
        #return sum([len("".join(i)) for i in regex_url.findall(sentence)]) < 15
        return  len(regex_url.findall(sentence) )== 0


    def c_no_breadcrumbs(self, sentence, side):
        return len(regex_breadcrumbs1.findall(sentence)) < 3 \
                or len(regex_breadcrumbs2.findall(sentence)) < 2

    def c_no_unicode_noise(self, sentence, side):
        lang = self.src_lang
        if side == "right":
            lang = self.trg_lang

        # Icelandic can have words with three or four high unicode values like 'þýðir'
        # Finish sometimes too
        if lang in ('is', 'fi'):
            return len(regex_unicode_noise_relaxed.findall(sentence)) == 0
        else:
            return len(regex_unicode_noise.findall(sentence)) == 0

    def c_no_space_noise(self, sentence, side):
        return len(regex_spaces_noise.findall(sentence)) == 0

    def c_no_paren(self,left, right):
        if len(re.findall(regex_paren, left)) or len(re.findall(regex_paren, right)): #there are parentheses
            l_char_count = {i: left.count(i) for i in set(left)}
            r_char_count = {i: right.count(i) for i in set(right)}
            if (((l_char_count.get("[") or 0) + (l_char_count.get("]") or 0)) > 6 ) or (l_char_count.get("[") or 0) != (l_char_count.get("]") or 0): #max 6 [ or ], having the same [ and ] 
                return False
            if (((r_char_count.get("[") or 0) + (r_char_count.get("]") or 0)) > 6 ) or (r_char_count.get("[") or 0) != (r_char_count.get("]") or 0): #max 6 [ or ], having the same [ and ] 
                return False                
            if (((l_char_count.get("{") or 0) + (l_char_count.get("}") or 0)) > 6 ) or (l_char_count.get("{") or 0) != (l_char_count.get("}") or 0): #max than 6 { or }, having the same { and }
                return False
            if (((r_char_count.get("{") or 0) + (r_char_count.get("}") or 0)) > 6 ) or (r_char_count.get("{") or 0) != (r_char_count.get("}") or 0): #max than 6 { or }, having the same { and }
                return False                
            if (((l_char_count.get("⟨") or 0) + (l_char_count.get("⟩") or 0)) > 6 ) or (l_char_count.get("⟨") or 0) != (l_char_count.get("⟩") or 0): #max than 6 ⟨ or ⟩, having the same ⟨ and ⟩            
                return False
            if (((r_char_count.get("⟨") or 0) + (r_char_count.get("⟩") or 0)) > 6 ) or (r_char_count.get("⟨") or 0) != (r_char_count.get("⟩") or 0): #max than 6 ⟨ or ⟩, having the same ⟨ and ⟩            
                return False                
            l_opening_paren = l_char_count.get("(") or 0
            r_opening_paren = r_char_count.get("(") or 0
            l_closing_paren = l_char_count.get(")") or 0
            r_closing_paren = r_char_count.get(")") or 0
            if (l_opening_paren == l_closing_paren) and (r_opening_paren == r_closing_paren): #any amount of  () is allowed, as long as there are the same amount of  ( and )
                return True
            elif l_closing_paren == r_closing_paren:     #if not the same amount, the closing ) must match in source and target, to allow  sentences as a)..., b)..., etc
                return True
            else:
                return False                
        return True    


    def c_no_literals(self, sentence, side):
        return not any(l in sentence for l in self.config["no_literals"])

    def c_no_escaped_unicode(self, sentence, side):
        return len(regex_escaped_unicode.findall(sentence)) == 0

    def c_no_glued_words(self, sentence, side):
        return regex_glued_words.search(sentence) == None

    def c_no_repeated_words(self, sentence, side):
        lang = self.src_lang
        if side == "right":
            lang = self.trg_lang

        our_regex = regex_repeated_without_words
        if lang in safe_noise_detection_langs:
            our_regex = regex_repeated_words

        min_chars = 7
        if lang in CJK:
            min_chars = 4

        for match_obj in regex.finditer(our_regex, sentence):
            matching = match_obj.group().strip()
            # if match does not have a minimum length continue without discarding
            if len(matching) > min_chars:
                r2 = regex.search("[[:alpha:]]", matching)
                if r2:
                    return False
        return True

    def c_no_porn(self, left, right):
        if self.porn_removal is None:
            return True
    
        if self.porn_removal_side == "sl":
            tok = self.porn_tokenizer.tokenize(left.lower())
        elif self.porn_removal_side == "tl":
            tok = self.porn_tokenizer.tokenize(right.lower())
        else:
            raise Exception(f"c_no_porn rule needs 'sl' or 'tl' param, not {self.porn_removal_side}")

        return self.porn_removal.predict(self.porn_tokenizer.detokenize(tok))[0][0] == '__label__negative'


    def c_no_number_inconsistencies(self, left, right):
        left_nums =  re.sub('[^0-9]','', left)
        right_nums = re.sub('[^0-9]','', right)
        
        sorted_left_nums = ''.join(sorted(left_nums))
        sorted_right_nums = ''.join(sorted(right_nums))
        
        if sorted_left_nums == sorted_right_nums:
            return True
        else:
            return False
        
    def c_no_script_inconsistencies(self, sentence, side):
        found_script_family = ""
        
        for c in sentence:
            if c.isalpha():
                family = script_family(c)
                if family == "":
                    continue            
                if found_script_family == "":
                    #first char's script
                    found_script_family =  family
                    continue
                if found_script_family != family:
                    return False
                else:
                    continue
    
        return True                
        
