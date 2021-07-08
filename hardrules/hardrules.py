import unicodedata
import logging
import regex
import sys
from fastspell import FastSpell

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
safe_noise_detection_langs = {"en", "es", "fr", "pl", "de", "it", "pt", "nl", "cs", "ro", "fi", "lv", "et", "bg", "hr", "da", "hu", "ga", "eu", "gl", "sl", "sv", "mt", "sk"}

safe_noise_detection_langs = {"en", "es", "fr", "pl", "de", "it", "pt", "nl", "cs", "ro", "fi", "lv", "et", "bg", "hr", "da", "hu", "ga", "eu", "gl", "sl", "sv", "mt", "sk", "is", "lt", "nb", "nn", "no"}
#similar_pairs = [{"es","ca"}, {"es","gl"}, {"pt","gl"}, {"no","nn"}, {"no", "da"}]
atilde_langs = {"pt"}
acumflex_langs = {"cy", "fr", "fa", "it", "pt", "tr", "vi",}

def c_identical_alpha(left, right):
    left = left.translate(tbl_non_alpha)
    right = right.translate(tbl_non_alpha)
    return left.casefold() != right.casefold()

def c_minimal_length(sentence):
    """ Counts number of whitespace, requires >= 2 (3 words) """
    return len(regex_blank.findall(sentence)) >= 2

def c_length(left, right):
    return 0.5 <= float(len(left))/float(len(right)) <= 2.0

def c_length_bytes(left, right):
    return 0.5 <= float(len(left.encode("utf8")))/float(len(right.encode("utf8"))) <= 2.0
'''
def c_different_language(left, right, left_lang, right_lang):
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
def c_reliable_long_language(sentence, language):
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
def c_no_bad_encoding(sentence, lang):
    if lang not in atilde_langs and 'Ã' in sentence:
        return False
    if lang not in acumflex_langs and 'Â' in sentence:
        return False
    return True

def c_alpha(sentence):
    return len(regex_alpha.findall(sentence)) > 0
    
def c_majority_alpha(sentence):
    return float(len(regex_alpha.findall(sentence))) / float(len(sentence)) >= 0.5

def c_no_urls(sentence):
    return sum([len("".join(i)) for i in regex_url.findall(sentence)]) < 15

#def c_no_breadcrumbs(sentence):
#    return len(regex_breadcrumbs.findall(sentence)) < 3


def c_no_breadcrumbs1(sentence):
    return len(regex_breadcrumbs1.findall(sentence)) < 3  

def c_no_breadcrumbs2(sentence):
    return len(regex_breadcrumbs2.findall(sentence)) < 2  

def c_no_noise(sentence):
    return len(regex_unicode_noise.findall(sentence)) == 0
    
def c_no_space_noise(sentence):
    return len(regex_spaces_noise.findall(sentence)) == 0
    
def c_no_paren(sentence):
    return len(regex_paren.findall(sentence)) < 10

def c_unwanted(sentence):
    return len(regex_unwanted.findall(sentence)) < 5

def c_inconditional(sentence):
    return len(regex_inconditional.findall(sentence)) < 1

def c_no_literals(literals, sentence):
    return not any(l in sentence for l in literals)

def c_no_escaped_unicode(sentence):
    return len(regex_escaped_unicode.findall(sentence)) == 0

def c_no_glued_words(sentence):
    return regex_glued_words.search(sentence) == None

def c_no_porn(left, right, model, side, porn_tokenizer):
    if side == "sl":
        tok = porn_tokenizer.tokenize(left.lower())
    else:
        tok = porn_tokenizer.tokenize(right.lower())
    return model.predict(porn_tokenizer.detokenize(tok))[0][0] == '__label__negative'

def wrong_tu(left, right, args, lm_filter = None, porn_removal = None, porn_tokenizer = None, fastspell_src = None, fastspell_trg = None):
    if not left:
        return "c_no_empty(left)"
    if not right:
        return "c_no_empty(right)"
    if len(left) >= 1024:
        return "len(left) >= 1024"
    if len(right) >= 1024:
        return "len(right) >= 1024"
    elif not c_no_literals(["Re:"], left):
        return "c_no_literals(['Re:'], left)"
    elif not c_no_literals(["Re:"], right):
        return "c_no_literals(['Re:'], right)"            
    elif not args.disable_minimal_length and not (c_minimal_length(left) or c_minimal_length(right)):
        return "c_minimal_length(left) and c_minimal_length(right)"
    elif not (c_length(left, right) or c_length_bytes(left, right)): 
        return "c_length or c_length_bytes"
    elif not c_identical_alpha(left, right):
        return "c_identical_alpha"
#    elif (not args.disable_lang_ident and not  c_different_language(left, right, args.source_lang, args.target_lang)):
#        return "c_different_language"
    elif not c_majority_alpha(left):
        return "c_majority_alpha(left)"
    elif not c_majority_alpha(right):
        return "c_majority_alpha(right)"
    elif not c_no_urls(left):
        return "c_no_urls(left)"
    elif not c_no_urls(right):
        return "c_no_urls(right)"
    #elif not c_no_breadcrumbs(left):    
    #    return "c_no_breadcrumbs(left)"
    #elif not c_no_breadcrumbs(right):
    #    return "c_no_breadcrumbs(right)"
    elif not c_no_breadcrumbs1(left):
        return "c_no_breadcrumbs1(left)"
    elif not c_no_breadcrumbs1(right):
        return "c_no_breadcrumbs1(right)"
    elif not c_no_breadcrumbs2(left):
        return "c_no_breadcrumbs2(left)"
    elif not c_no_breadcrumbs2(right):
        return "c_no_breadcrumbs2(right)"       
    elif not c_no_glued_words(left):
        return "c_no_glued_words(left)"
    elif not c_no_glued_words(right):
        return "c_no_glued_words(right)"    
    elif args.source_lang in safe_noise_detection_langs and not c_no_noise(left):
        return "args.source_lang in safe_noise_detection_langs and not c_no_noise(left)" 
    elif args.target_lang in safe_noise_detection_langs and not c_no_noise(right):
        return "args.target_lang in safe_noise_detection_langs and not c_no_noise(right)"
    elif not c_no_space_noise(left):
        return "c_no_space_noise(left)"
    elif not c_no_space_noise(right):
        return "c_no_space_noise(right)"
    elif not c_no_paren(left):
        return "c_no_paren(left)"
    elif not c_no_paren(right):
        return "c_no_paren(right)"
    elif not c_unwanted(left):
        return "c_unwanted(left)"
    elif not c_unwanted(right):
        return "c_unwanted(right)"
    elif not c_inconditional(left):
        return "c_inconditional(left)"
    elif not c_inconditional(right):
        return "c_inconditional(right)"
    elif not c_no_escaped_unicode(left):
        return "c_no_escaped_unicode(left)"
    elif not c_no_escaped_unicode(right):
        return "c_no_escaped_unicode(right)"
    elif not c_no_literals(["{{", "%s", "}}"], left):
        return 'c_no_literals(["{{", "%s", "}}"], left)'
    elif not c_no_literals(["{{", "%s", "}}"], right):
        return 'c_no_literals(["{{", "%s", "}}"], right)'
    elif not c_no_bad_encoding(left, args.source_lang) and not c_no_bad_encoding(right, args.target_lang):
        return 'c_no_bad_encoding(["Â","Ã"])'
    elif left.istitle() and right.istitle():
        return 'left.istitle() and right.istitle()'
#    elif (not args.disable_lang_ident and not  c_reliable_long_language(left, args.source_lang)):
#        return "c_reliable_long_language(left, sourcelang)"
#    elif (not args.disable_lang_ident and  not c_reliable_long_language(right, args.target_lang)):
#        return "c_reliable_long_language(right, targetlang)"
    elif (not args.disable_lang_ident and not  fastspell_src.getlang(left)==args.source_lang):
        return "c_wrong_language(left, sourcelang)"
    elif (not args.disable_lang_ident and  not fastspell_trg.getlang(right)==args.target_lang):
        return "c_wrong_language(right, targetlang)"
    elif not args.disable_porn_removal and porn_removal != None and not c_no_porn(left, right, porn_removal, args.metadata_yaml['porn_removal_side'], porn_tokenizer):
        return "c_no_porn"
    elif  args.disable_lm_filter == False and lm_filter != None and lm_filter.score(left, right) < args.lm_threshold:
        return "lm_filter.score(left, right) < args.lm_threshold"
    return False
