from tempfile import TemporaryFile, NamedTemporaryFile
import fasttext
import logging
import random
import typing
import os

try:
    from .util import shuffle_file
except (SystemError, ImportError):
    from util import shuffle_file


def shuffle_lm_training_text(input: typing.TextIO,dev_size: int ) -> (str,str,str,str):
    dev_sl=NamedTemporaryFile("w",delete=False)
    dev_tl=NamedTemporaryFile("w",delete=False)
    train_sl=NamedTemporaryFile("w",delete=False)
    train_tl=NamedTemporaryFile("w",delete=False)

    with TemporaryFile("w+") as temp_sl, TemporaryFile("w+") as temp_tl, TemporaryFile("w+") as shuf_sl, TemporaryFile("w+") as shuf_tl:
        #Read tab-separated input and write its content into two different files
        for line in input:
            parts=line.rstrip("\n").split("\t")
            line_sl=parts[0]
            line_tl=parts[1]
            temp_sl.write(line_sl)
            temp_sl.write("\n")
            temp_tl.write(line_tl)
            temp_tl.write("\n")
        temp_sl.flush()
        temp_tl.flush()
        temp_sl.seek(0)
        temp_tl.seek(0)

        #Shuffle the independent files
        shuffle_file(temp_sl, shuf_sl)
        shuffle_file(temp_tl, shuf_tl)

        #read them and split between dev and train
        shuf_sl.seek(0)
        shuf_tl.seek(0)

        for i in range(dev_size):
            line=shuf_sl.readline()
            dev_sl.write(line)

            line=shuf_tl.readline()
            dev_tl.write(line)

        for line in shuf_sl:
            train_sl.write(line)

        for line in shuf_tl:
            train_tl.write(line)

    dev_sl.close()
    dev_tl.close()
    train_sl.close()
    train_tl.close()

    return train_sl.name, train_tl.name, dev_sl.name, dev_tl.name


def train_fluency_filter(args):
    # Prepare corpora:
    # Input corpora for training the classifier split in 2 parts:
    #  - Training data for LM
    #  - Validation set for estimating perplexity of clean text
    # Input noisy corpus used as validation set for estimating perplexity of noisy text

    if not (args.lm_file_sl and args.lm_file_tl):
        return None

    # Load lm modules only when needed
    try:
        from .lm import DualLMFluencyFilter,LMType, DualLMStats
    except (SystemError, ImportError):
        from lm import DualLMFluencyFilter,LMType, DualLMStats

    logging.info("Training LM-based fluency filter.")

    inputIsTmp=True
    if args.lm_training_file_sl and args.lm_training_file_tl and args.lm_clean_examples_file_sl and args.lm_clean_examples_file_tl:
        inputIsTmp=False
        lm_train_path_sl=args.lm_training_file_sl
        lm_train_path_tl=args.lm_training_file_tl
        lm_dev_clean_sl=args.lm_clean_examples_file_sl
        lm_dev_clean_tl=args.lm_clean_examples_file_tl
        logging.info("SL LM training corpus: {}".format(lm_train_path_sl))
        logging.info("TL LM training corpus: {}".format(lm_train_path_tl))
        logging.info("SL LM dev clean corpus: {}".format(lm_dev_clean_sl))
        logging.info("TL LM dev clean corpus: {}".format(lm_dev_clean_tl))
        logging.info("SL LM dev noisy corpus: {}".format(args.noisy_examples_file_sl))
        logging.info("TL LM dev noisy corpus: {}".format(args.noisy_examples_file_tl))
    else:
        logging.info("SL & TL LM training corpora have been obtained from tab-separated input file (the same ones used for training the classifier), after randomly removing {} sentences.".format(args.lm_dev_size))
        logging.info("SL & TL LM dev clean corpora have been randomly selected from input input file (the same used for training the classifier): {} sentences.".format(args.lm_dev_size))
        lm_train_path_sl,lm_train_path_tl, lm_dev_clean_sl, lm_dev_clean_tl = shuffle_lm_training_text(args.input,args.lm_dev_size)

        if not (args.noisy_examples_file_sl):
            #build synthetic noise
            args.noisy_examples_file_sl = shuffle_chars(lm_train_path_sl)
        logging.info("SL LM dev noisy corpus: {}".format(args.noisy_examples_file_sl))

        if not (args.noisy_examples_file_tl):
            #build synthetic noise
            args.noisy_examples_file_tl = shuffle_chars(lm_train_path_tl)
        logging.info("TL LM dev noisy corpus: {}".format(args.noisy_examples_file_tl))

    try:
        ff=DualLMFluencyFilter(LMType.CHARACTER,args.source_lang, args.target_lang, args.source_tokenizer_command, args.target_tokenizer_command)
        stats=ff.train(lm_train_path_sl, lm_train_path_tl,lm_dev_clean_sl,lm_dev_clean_tl, args.noisy_examples_file_sl,args.noisy_examples_file_tl, args.lm_file_sl, args.lm_file_tl)
    finally:
        if inputIsTmp:
            os.remove(lm_train_path_sl)
            os.remove(lm_train_path_tl)
            os.remove(lm_dev_clean_sl)
            os.remove(lm_dev_clean_tl)
    return stats

# Porn removal classifier
# training, compressing, run tests and save model file
def train_porn_removal(args):
    if args.porn_removal_train is None or args.porn_removal_file is None:
        return

    logging.info("Training porn removal classifier.")
    model = fasttext.train_supervised(args.porn_removal_train.name,
                                    thread=args.processes,
                                    lr=1.0,
                                    epoch=25,
                                    minCount=5,
                                    wordNgrams=1,
                                    verbose=0)
    logging.info("Compressing classifier.")
    model.quantize(args.porn_removal_train.name,
                retrain=True,
                thread=args.processes,
                verbose=0)

    if args.porn_removal_test is not None:
        N, p, r = model.test(args.porn_removal_test.name, threshold=0.5)
        logging.info("Precision:\t{:.3f}".format(p))
        logging.info("Recall:\t{:.3f}".format(r))

    logging.info("Saving porn removal classifier.")
    model.save_model(args.porn_removal_file)

#Randomizes sentences' characters in a file
def shuffle_chars(input_file_path):
    logging.debug("Shuffling {0} to get noisy corpus".format(input_file_path))
    noisy_file = NamedTemporaryFile("w+", delete=False)
    logging.debug("Writing noisy file to {0}".format(noisy_file.name))    
    with open (input_file_path,  "r+") as i:
        for line in i:
            s = line.strip()
            noisy_file.write(''.join(random.sample(s,len(s)))+"\n")

        i.flush()
        i.seek(0)

        noisy_file.flush()
        noisy_file.seek(0)

    return noisy_file.name
