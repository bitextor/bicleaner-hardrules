import unicodedata
import logging
import regex
import sys
from fastspell import FastSpell
from collections import OrderedDict
from inspect import getmembers, signature
from copy import deepcopy

try:
    from .lm import load_lm_filter
    from .tokenizer import Tokenizer
except (SystemError, ImportError):
    from lm import load_lm_filter
    from tokenizer import Tokenizer 

tbl_non_alpha = [chr(i) for i in range(sys.maxunicode) if not unicodedata.category(chr(i)).startswith('L')]
tbl_non_alpha = str.maketrans('', '', ''.join(tbl_non_alpha))
regex_blank = regex.compile("[ \u00A0]")
regex_alpha = regex.compile("[[:alpha:]]")
regex_url = regex.compile('((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]|\((:?[^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
#regex_breadcrumbs = regex.compile("([ ][-/»][ ]|[|<>→←]|[ ][:][:][ ])")
regex_breadcrumbs1 = regex.compile("([ ][-/][ ]|[<>*]|[ ][:][ ])")
regex_breadcrumbs2 = regex.compile("([ ][»][ ]|[|→←•·¬])")
regex_unicode_noise = regex.compile("[\x80-\xFF]{3,}")
regex_spaces_noise = regex.compile("([ ].){4,}[ ]")
regex_paren = regex.compile("[][(){}]")
regex_unwanted = regex.compile("[+*]")
regex_inconditional = regex.compile("=\"")
regex_escaped_unicode = regex.compile("[\\\\]u[0-9a-fA-F]{3,}")
#regex_glued_words = regex.compile("\b[[:alpha:]]*[[:lower:]][[:upper:]][[:alpha:]]*)
regex_glued_words = regex.compile("([[:alpha:]]*[[:upper:]]{1}[[:lower:]]+){3}")
regex_repeated_words = regex.compile(r"\b([^\W\d]+)\s+\1+\b")
safe_noise_detection_langs = {"en", "es", "fr", "pl", "de", "it", "pt", "nl", "cs", "ro", "fi", "lv", "et", "bg", "hr", "da", "hu", "ga", "eu", "gl", "sl", "sv", "mt", "sk"}

safe_noise_detection_langs = {"en", "es", "fr", "pl", "de", "it", "pt", "nl", "cs", "ro", "fi", "lv", "et", "bg", "hr", "da", "hu", "ga", "eu", "gl", "sl", "sv", "mt", "sk", "is", "lt", "nb", "nn", "no"}
#similar_pairs = [{"es","ca"}, {"es","gl"}, {"pt","gl"}, {"no","nn"}, {"no", "da"}]
atilde_langs = {"pt"}
acumflex_langs = {"cy", "fr", "fa", "it", "pt", "tr", "vi",}

class Hardrules():
    # Define default settings
    # the order of execution will be the order of the dict
    rule_pipeline = OrderedDict()
    rule_pipeline['no_empty'] = True
    rule_pipeline['max_char_length'] = 1024
    rule_pipeline['min_word_length'] = 3
    rule_pipeline['length'] = True
    rule_pipeline['length_bytes'] = True
    rule_pipeline['identical_alpha'] = True
    rule_pipeline['no_literals'] = ["Re:","{{", "%s", "}}"]
    rule_pipeline['majority_alpha'] = True
    rule_pipeline['no_urls'] = True
    rule_pipeline['no_breadcrumbs1'] = True
    rule_pipeline['no_breadcrumbs2'] = True
    rule_pipeline['no_glued_words'] = True
    rule_pipeline['no_repeated_words'] = True
    rule_pipeline['no_noise'] = True
    rule_pipeline['no_space_noise'] = True
    rule_pipeline['no_paren'] = True
    rule_pipeline['unwanted'] = True
    rule_pipeline['inconditional'] = True
    rule_pipeline['no_escaped_unicode'] = True
    rule_pipeline['no_bad_encoding'] = True
    rule_pipeline['no_titles'] = True
    rule_pipeline['wrong_language'] = True
    rule_pipeline['no_porn'] = 'sl'
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
            self.porn_removal_side = args.metadata_yaml['porn_removal_side']
            self.porn_removal = args.porn_removal
            if self.porn_removal_side == 'tl':
                self.porn_tokenizer = Tokenizer(args.target_tokenizer_command,
                                                args.target_lang)
            else:
                self.porn_tokenizer = Tokenizer(args.source_tokenizer_command,
                                                args.source_lang)
        else:
            self.porn_removal = None
            self.porn_tokenizer = None
            self.porn_removal_side = None

        # Load FastSpell
        if not args.disable_lang_ident:
            self.fastspell_src = FastSpell.FastSpell(args.source_lang, mode="cons")
            self.fastspell_trg = FastSpell.FastSpell(args.target_lang, mode="cons")
        else:
            self.fastspell_src = None
            self.fastspell_trg = None

        self.src_lang = args.source_lang
        self.trg_lang = args.target_lang
        self.run_all_rules = args.run_all_rules
        self.disable_minimal_length = args.disable_minimal_length
        self.rules = {n: f for n, f in getmembers(self) if n.startswith('c_')}
        logging.debug(f"Enabled rules: {self.rules.keys()}")

        # Create dict with with config
        self.config = deepcopy(self.rule_pipeline)
        if args.config is not None:
            # Validate config
            dif = args.config.keys() - self.rule_pipeline.keys()
            if dif:
                raise Exception(f"Unkown options in config: {dif}")

            # Overwrite with user-defined options
            for name, param in args.config.items():
                self.config[name] = param

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
            logging.debug(f"Rule: {rule_name}")

            # Obtain function to be applied
            rule_func = self.rules['c_' + rule_name]

            # Determine if rule has to be applied to both sides separated, or together
            #TODO is reflection slow?
            if 'sentence' in signature(rule_func).parameters:
                # Iterate over left and right side
                for sidename, side in {'left': left, 'right': right}.items():
                    keep = rule_func(side, sidename)
                    logging.debug(f"Side: {sidename}")
                    logging.debug(f"Keep: {keep}")
                    if not keep and self.run_all_rules:
                        discards.append(f"{rule_name}({sidename})")
                        # Especial case for empty rule to avoid crashes in other rules
                        if rule_name == 'no_empty':
                            return discards
                    elif not keep:
                        return f"{rule_name}({sidename})"
            else:
                # Apply rule to both sides
                keep = rule_func(left, right)
                logging.debug(f"Keep: {keep}")
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

    def c_no_titles(self, sentence, side):
        return not sentence.istitle()

    def c_max_char_length(self, sentence, side):
        return len(sentence) < self.config['max_char_length']

    def c_min_word_length(self, sentence, side):
        if self.disable_minimal_length:
            return True
        """ Counts number of whitespace, requires >= 2 (3 words) """
        return len(regex_blank.findall(sentence)) >= self.config['min_word_length']-1

    def c_identical_alpha(self, left, right):
        left = left.translate(tbl_non_alpha)
        right = right.translate(tbl_non_alpha)
        return left.casefold() != right.casefold()

    def c_length(self, left, right):
        return 0.5 <= float(len(left))/float(len(right)) <= 2.0

    def c_length_bytes(self, left, right):
        return 0.5 <= float(len(left.encode("utf8")))/float(len(right.encode("utf8"))) <= 2.0

    def c_wrong_language(self, sentence, side='left'):
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
        return self.lm_filter.score(left, right) < self.lm_threshold

    '''
    def c_different_language(self, left, right, left_lang, right_lang):
        if left_lang =="nb":
            left_lang="no"

        if right_lang=="nb":
            right_lang="no"
            

        l_reliable = False
        l_bytes = 0
        l_details = ()
     
        try:
            l_reliable, l_bytes, l_details = pycld2.detect(left)
        except:
            return False # encoding error -> noise

        r_reliable = False
        r_bytes = 0
        r_details = ()

        try:
            r_reliable, r_bytes, r_details = pycld2.detect(right)
        except:
            return False # encoding error -> noise
            
        if l_reliable and r_reliable and l_details[0][1] != r_details[0][1]:    
            return True
        elif not l_reliable or not r_reliable:
            return True
        else:
            #both langs are reliable at this point, and the identified language is the same for left and right
            identified = l_details[0][1]
            if (identified in [left_lang, right_lang]  and {left_lang, right_lang} in similar_pairs):
                return True
            else:    
                return False
    '''
    '''        
    def c_reliable_long_language(self, sentence, language):
        if language=="nb":
            language = "no"
            
        reliable = False
        bytes = 0
        details = ()
        
        try:
            reliable, bytes, details = pycld2.detect(sentence)
        except:
            return True # encoding error -> noise
        
        if len(sentence) > 30 and reliable and details[0][1] != language:
            if {language, details[0][1]} in similar_pairs:
                return True
            else:
                return False
        else:
            return True
    '''
    def c_no_bad_encoding(self, sentence, side):
        lang = self.src_lang if side == 'left' else self.trg_lang

        if lang not in atilde_langs and 'Ã' in sentence:
            return False
        if lang not in acumflex_langs and 'Â' in sentence:
            return False
        return True

    def c_alpha(self, sentence, side):
        return len(regex_alpha.findall(sentence)) > 0
        
    def c_majority_alpha(self, sentence, side):
        return float(len(regex_alpha.findall(sentence))) / float(len(sentence)) >= 0.5

    def c_no_urls(self, sentence, side):
        return sum([len("".join(i)) for i in regex_url.findall(sentence)]) < 15

    #def c_no_breadcrumbs(self, sentence, side):
    #    return len(regex_breadcrumbs.findall(sentence)) < 3


    def c_no_breadcrumbs1(self, sentence, side):
        return len(regex_breadcrumbs1.findall(sentence)) < 3  

    def c_no_breadcrumbs2(self, sentence, side):
        return len(regex_breadcrumbs2.findall(sentence)) < 2  

    def c_no_noise(self, sentence, side):
        return len(regex_unicode_noise.findall(sentence)) == 0
        
    def c_no_space_noise(self, sentence, side):
        return len(regex_spaces_noise.findall(sentence)) == 0
        
    def c_no_paren(self, sentence, side):
        return len(regex_paren.findall(sentence)) < 10

    def c_unwanted(self, sentence, side):
        return len(regex_unwanted.findall(sentence)) < 5

    def c_inconditional(self, sentence, side):
        return len(regex_inconditional.findall(sentence)) < 1

    def c_no_literals(self, sentence, side):
        return not any(l in sentence for l in self.config["no_literals"])

    def c_no_escaped_unicode(self, sentence, side):
        return len(regex_escaped_unicode.findall(sentence)) == 0

    def c_no_glued_words(self, sentence, side):
        return regex_glued_words.search(sentence) == None

    def c_no_repeated_words(self, sentence, side):
        return regex_repeated_words.search(sentence) == None

    def c_no_porn(self, left, right):
        if self.porn_removal is None:
            return True

        if self.porn_removal_side == "sl":
            tok = self.porn_tokenizer.tokenize(left.lower())
        elif self.porn_removal_side == "tl":
            tok = self.porn_tokenizer.tokenize(right.lower())
        else:
            raise Exception(f"c_no_porn rule needs 'sl' or 'tl' param, not {self.porn_removal_side}")
        logging.debug(self.porn_removal.predict(self.porn_tokenizer.detokenize(tok))[0][0])
        return self.porn_removal.predict(self.porn_tokenizer.detokenize(tok))[0][0] == '__label__negative'

#def wrong_tu(left, right, args, lm_filter = None, porn_removal = None, porn_tokenizer = None, fastspell_src = None, fastspell_trg = None):
#    if not left:
#        return "c_no_empty(left)"
#    if not right:
#        return "c_no_empty(right)"
#    if len(left) >= 1024:
#        return "len(left) >= 1024"
#    if len(right) >= 1024:
#        return "len(right) >= 1024"
#    elif not c_no_literals(["Re:"], left):
#        return "c_no_literals(['Re:'], left)"
#    elif not c_no_literals(["Re:"], right):
#        return "c_no_literals(['Re:'], right)"            
#    elif not args.disable_minimal_length and not (c_minimal_length(left) or c_minimal_length(right)):
#        return "c_minimal_length(left) and c_minimal_length(right)"
#    elif not (c_length(left, right) or c_length_bytes(left, right)): 
#        return "c_length or c_length_bytes"
#    elif not c_identical_alpha(left, right):
#        return "c_identical_alpha"
##    elif (not args.disable_lang_ident and not  c_different_language(left, right, args.source_lang, args.target_lang)):
##        return "c_different_language"
#    elif not c_majority_alpha(left):
#        return "c_majority_alpha(left)"
#    elif not c_majority_alpha(right):
#        return "c_majority_alpha(right)"
#    elif not c_no_urls(left):
#        return "c_no_urls(left)"
#    elif not c_no_urls(right):
#        return "c_no_urls(right)"
#    #elif not c_no_breadcrumbs(left):    
#    #    return "c_no_breadcrumbs(left)"
#    #elif not c_no_breadcrumbs(right):
#    #    return "c_no_breadcrumbs(right)"
#    elif not c_no_breadcrumbs1(left):
#        return "c_no_breadcrumbs1(left)"
#    elif not c_no_breadcrumbs1(right):
#        return "c_no_breadcrumbs1(right)"
#    elif not c_no_breadcrumbs2(left):
#        return "c_no_breadcrumbs2(left)"
#    elif not c_no_breadcrumbs2(right):
#        return "c_no_breadcrumbs2(right)"       
#    elif not c_no_glued_words(left):
#        return "c_no_glued_words(left)"
#    elif not c_no_glued_words(right):
#        return "c_no_glued_words(right)"    
#    elif args.source_lang in safe_noise_detection_langs and not c_no_noise(left):
#        return "args.source_lang in safe_noise_detection_langs and not c_no_noise(left)" 
#    elif args.target_lang in safe_noise_detection_langs and not c_no_noise(right):
#        return "args.target_lang in safe_noise_detection_langs and not c_no_noise(right)"
#    elif not c_no_space_noise(left):
#        return "c_no_space_noise(left)"
#    elif not c_no_space_noise(right):
#        return "c_no_space_noise(right)"
#    elif not c_no_paren(left):
#        return "c_no_paren(left)"
#    elif not c_no_paren(right):
#        return "c_no_paren(right)"
#    elif not c_unwanted(left):
#        return "c_unwanted(left)"
#    elif not c_unwanted(right):
#        return "c_unwanted(right)"
#    elif not c_inconditional(left):
#        return "c_inconditional(left)"
#    elif not c_inconditional(right):
#        return "c_inconditional(right)"
#    elif not c_no_escaped_unicode(left):
#        return "c_no_escaped_unicode(left)"
#    elif not c_no_escaped_unicode(right):
#        return "c_no_escaped_unicode(right)"
#    elif not c_no_literals(["{{", "%s", "}}"], left):
#        return 'c_no_literals(["{{", "%s", "}}"], left)'
#    elif not c_no_literals(["{{", "%s", "}}"], right):
#        return 'c_no_literals(["{{", "%s", "}}"], right)'
#    elif not c_no_bad_encoding(left, args.source_lang) and not c_no_bad_encoding(right, args.target_lang):
#        return 'c_no_bad_encoding(["Â","Ã"])'
#    elif left.istitle() and right.istitle():
#        return 'left.istitle() and right.istitle()'
##    elif (not args.disable_lang_ident and not  c_reliable_long_language(left, args.source_lang)):
##        return "c_reliable_long_language(left, sourcelang)"
##    elif (not args.disable_lang_ident and  not c_reliable_long_language(right, args.target_lang)):
##        return "c_reliable_long_language(right, targetlang)"
#    elif (not args.disable_lang_ident and not  fastspell_src.getlang(left)==args.source_lang):
#        return "c_wrong_language(left, sourcelang)"
#    elif (not args.disable_lang_ident and  not fastspell_trg.getlang(right)==args.target_lang):
#        return "c_wrong_language(right, targetlang)"
#    elif not args.disable_porn_removal and porn_removal != None and not c_no_porn(left, right, porn_removal, args.metadata_yaml['porn_removal_side'], porn_tokenizer):
#        return "c_no_porn"
#    elif  args.disable_lm_filter == False and lm_filter != None and lm_filter.score(left, right) < args.lm_threshold:
#        return "lm_filter.score(left, right) < args.lm_threshold"
#    return False
