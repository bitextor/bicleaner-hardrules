#!/usr/bin/env python

import argparse
import io
import logging
import os
import sys
import traceback
import yaml
import fasttext
from fastspell import FastSpell

from heapq import heappush, heappop
from multiprocessing import Queue, Process, Value, cpu_count
from tempfile import NamedTemporaryFile, gettempdir
from timeit import default_timer

#Allows to load modules while inside or outside the package
try:
    from .util import logging_setup, check_positive, check_positive_between_zero_and_one
    from .hardrules import wrong_tu
    from .lm import DualLMFluencyFilter,LMType, DualLMStats
    from .tokenizer import Tokenizer
except (SystemError, ImportError):
    from util import logging_setup, check_positive, check_positive_between_zero_and_one
    from hardrules import wrong_tu
    from lm import DualLMFluencyFilter,LMType, DualLMStats
    from tokenizer import Tokenizer 

__author__ = "Sergio Ortiz Rojas"
__version__ = "Version 1.0 # 24/05/2021 # Separate hardrules package from Bicleaner # Jaume Zaragoza"
__version__ = "Version 1.1 # 26/05/2021 # Load lm only when necessary # Jaume Zaragoza"
__version__ = "Version 1.3 # 05/07/2021 # FastSpell, bad encoding Ä, check identical with alphabetic and discard empty sides # Jaume Zaragoza"
__version__ = "Version 1.3.1 # 12/07/2021 # Fix PyPi release # Jaume Zaragoza"

logging_level = 0

def initialization():
    global logging_level
    
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), formatter_class=argparse.ArgumentDefaultsHelpFormatter, description=__doc__)
    parser.add_argument('input',  nargs='?', type=argparse.FileType('rt', errors="replace"), default=io.TextIOWrapper(sys.stdin.buffer, errors="replace"),  help="Tab-separated bilingual tagged file")
    parser.add_argument('output', nargs='?', type=argparse.FileType('wt'), default=sys.stdout, help="Output of the classification")
    parser.add_argument('--annotated_output',default=False, action='store_true', help="Adds an extra column with each sentence's evaluation (\"keep\" if the sentence is good, otherwise the reason for rejecting")

    #groupM = parser.add_argument_group('Mandatory')
    #groupM.add_argument("-s", "--source_lang", type=str, required=True, help="Source language (SL) of the input")
    #groupM.add_argument("-t", "--target_lang", type=str, required=True, help="Target language (TL) of the input")

    groupO = parser.add_argument_group('Optional')
    groupO.add_argument('--tmp_dir', default=gettempdir(), help="Temporary directory where creating the temporary files of this program")
    groupO.add_argument('-b', '--block_size', type=int, default=10000, help="Sentence pairs per block")
    groupO.add_argument('-p', '--processes', type=int, default=max(1, cpu_count()-1), help="Number of processes to use")

    groupO.add_argument('--score_only',action='store_true', help="Only output one column which is the hardrule tag: 0(keep) 1(discard)", default=False)
    groupO.add_argument('--disable_lang_ident', default=False, action='store_true', help="Don't apply rules that use language detecting")
    groupO.add_argument('--disable_minimal_length', default=False, action='store_true', help="Don't apply minimal length rule")
    groupO.add_argument('--disable_porn_removal', default=False, action='store_true', help="Don't apply porn removal")

    groupO.add_argument("-s", "--source_lang", type=str, default=None,  help="Source language (SL) of the input")
    groupO.add_argument("-t", "--target_lang", type=str, default=None,  help="Target language (TL) of the input")

    groupO.add_argument("--scol", default=1, type=check_positive, help ="Source sentence column (starting in 1)")
    groupO.add_argument("--tcol", default=2, type=check_positive, help ="Target sentence column (starting in 1)")  
    
    groupO.add_argument("-S", "--source_tokenizer_command", default=None, type=str, help="Source language (SL) tokenizer full command")
    groupO.add_argument("-T", "--target_tokenizer_command", default=None, type=str, help="Target language (TL) tokenizer full command")

    
    #LM  filtering
    groupO.add_argument('--disable_lm_filter', default=False, action='store_true', help="Don't apply LM filtering")
    groupO.add_argument('--metadata', type=argparse.FileType('r'), default=None, help="Bicleaner metadata (YAML file)")
    groupO.add_argument('--lm_threshold',type=check_positive_between_zero_and_one, default=0.5, help="Threshold for language model fluency scoring.")
    #groupO.add_argument('--keep_lm_result',action='store_true', help="Add an additional column to the results with the language model fluency score.")

    # Logging group
    groupL = parser.add_argument_group('Logging')
    groupL.add_argument('-q', '--quiet', action='store_true', help='Silent logging mode')
    groupL.add_argument('--debug', action='store_true', help='Debug logging mode')
    groupL.add_argument('--logfile', type=argparse.FileType('a'), default=sys.stderr, help="Store log to a file")
    groupL.add_argument('-v', '--version', action='version', version="%(prog)s " + __version__, help="show version of this script and exit")


    args = parser.parse_args()
    logging_setup(args)
    
    logging_level = logging.getLogger().level
    
    
    # Ensure that directory exists; if not, create it
    if not os.path.exists(args.tmp_dir):
        os.makedirs(args.tmp_dir)

        
    #Try loading metadata for LM filtering and porn removal
    if not (args.disable_lm_filter and args.disable_porn_removal) and args.metadata != None:
        logging.info("Loading metadata info")

        try:
            args.metadata_yaml = yaml.safe_load(args.metadata)
            args.metadata_yaml["yamlpath"] = os.path.dirname(os.path.abspath(args.metadata.name))

            if not ("source_lm" in args.metadata_yaml and "target_lm" in args.metadata_yaml):
                args.disable_lm_filter = True
                logging.warning("LM file not present in metadata.")
            if not ("porn_removal_file" in args.metadata_yaml):
                args.disable_porn_removal = True
                logging.warning("Porn removal classifier not present in metadata.")
            else:
                try:
                    args.porn_removal = fasttext.load_model(os.path.join(args.metadata_yaml["yamlpath"], args.metadata_yaml['porn_removal_file']))
                except:
                    args.porn_removal = fasttext.load_model(args.metadata_yaml['porn_removal_file'])

            if "source_tokenizer_command" in args.metadata_yaml:
                args.source_tokenizer_command=args.metadata_yaml["source_tokenizer_command"]
            if "target_tokenizer_command" in args.metadata_yaml:
                args.target_tokenizer_command=args.metadata_yaml["target_tokenizer_command"]                
    
            parser.set_defaults(**args.metadata_yaml)
            
        except:
            logging.warning("Error loading metadata.")
            args.disable_lm_filter  = True
            args.disable_porn_removal = True
            traceback.print_exc()
            #sys.exit(1)
    else:
        if args.metadata == None:
            logging.warning("Metadata file not provided.")
            args.disable_lm_filter = True
            args.disable_porn_removal = True

    if (args.source_lang == None or args.target_lang == None):
        if (args.metadata == None):
            logging.error("No source or target languages provided.")
            sys.exit(1)
        else:
            try:
                if not "metadata_yaml" in args  or args.metadata_yaml == None:
                    args.metadata_yaml = yaml.safe_load(args.metadata)
                #args.metadata_yaml["yamlpath"] = os.path.dirname(os.path.abspath(args.metadata.name))

                args.source_lang=args.metadata_yaml["source_lang"]
                args.target_lang=args.metadata_yaml["target_lang"]    
            except:
                traceback.print_exc()
                logging.error("Error retrieving source or target languages from metadata.")
                sys.exit(1)
                
    if args.disable_lm_filter:
        logging.info("LM filtering disabled.")
    if args.disable_porn_removal:
        logging.info("Porn removal disabled.")

    return args
    
def load_lm_filter(source_lang, target_lang, metadata_yaml, source_tokenizer_command, target_tokenizer_command):
    
    logging.debug("Loading LM filter")

    lmFilter = DualLMFluencyFilter( LMType[metadata_yaml['lm_type']], source_lang, target_lang, source_tokenizer_command, target_tokenizer_command)
    stats=DualLMStats(metadata_yaml['clean_mean_perp'], metadata_yaml['clean_stddev_perp'], metadata_yaml['noisy_mean_perp'], metadata_yaml['noisy_stddev_perp'] )

    fullpath_source_lm=os.path.join(metadata_yaml["yamlpath"], metadata_yaml['source_lm'])
    if os.path.isfile(fullpath_source_lm):
        source_lm = fullpath_source_lm
    else:
        source_lm = metadata_yaml['source_lm']
        
        
    fullpath_target_lm=os.path.join(metadata_yaml["yamlpath"], metadata_yaml['target_lm'])   
    if os.path.isfile(fullpath_target_lm):
        target_lm = fullpath_target_lm
    else:
        target_lm = metadata_yaml['target_lm']
    
    lmFilter.load(source_lm, target_lm, stats)
    
    return lmFilter

def reduce_process(output_queue, args):
    h = []
    last_block = 0
    while True:
        logging.debug("Reduce: heap status {0}".format(h.__str__()))
        while len(h) > 0 and h[0][0] == last_block:
            nblock, filein_name = heappop(h)
            last_block += 1

            with open(filein_name, 'r') as filein:
                for i in filein:
                    args.output.write(i)
                filein.close()
            os.unlink(filein_name)

        job = output_queue.get()
        if job:
            nblock, filein_name = job
            heappush(h, (nblock, filein_name))
        else:
            logging.debug("Exiting reduce loop")
            break

    if len(h) > 0:
        logging.debug("Still elements in heap")

    while len(h) > 0 and h[0][0] == last_block:
        nblock, filein_name = heapq.heappop(h)
        last_block += 1

        with open(filein_name, 'r') as filein:
            for i in filein:
                args.output.write(i)
            filein.close()

        os.unlink(filein_name)

    if len(h) != 0:
        logging.error("The queue is not empty and it should!")

    logging.info("Hard rules applied. Output available in {}".format(args.output.name))
    args.output.close()
    
def worker_process(i, jobs_queue, output_queue, args):
    if not args.disable_lm_filter:
        lm_filter = load_lm_filter(args.source_lang, args.target_lang, args.metadata_yaml, args.source_tokenizer_command, args.target_tokenizer_command)
    else:
        lm_filter = None

    if not args.disable_porn_removal:
        porn_removal = args.porn_removal
        if args.metadata_yaml['porn_removal_side'] == 'tl':
            porn_tokenizer = Tokenizer(args.target_tokenizer_command, args.target_lang)
        else:
            porn_tokenizer = Tokenizer(args.source_tokenizer_command, args.source_lang)
    else:
        porn_removal = None
        porn_tokenizer = None
        
    if not args.disable_lang_ident:
        fastspell_src = FastSpell.FastSpell(args.source_lang, mode="cons")
        fastspell_trg = FastSpell.FastSpell(args.target_lang, mode="cons")
    else:
        fastspell_src = None
        fastspell_trg = None    

    while True:
        job = jobs_queue.get()
        if job:
            logging.debug("Job {0}".format(job.__repr__()))
            nblock, filein_name = job
            ojob = None
            with open(filein_name, 'r') as filein, NamedTemporaryFile(mode="w", delete=False, dir=args.tmp_dir) as fileout:
                logging.debug("Classification: creating temporary filename {0}".format(fileout.name))

                for i in filein:
                    parts = i.rstrip('\n').split("\t")
                    left = ""
                    right= ""

                    if len(parts) >=  args.scol and len(parts) >= args.tcol:
                        left = parts[args.scol-1]
                        right = parts[args.tcol-1]
                        wrong_tu_results = wrong_tu(left,right, args, lm_filter, porn_removal, porn_tokenizer, fastspell_src, fastspell_trg)
                    else:
                        logging.error("scol ({}) or tcol ({}) indexes above column number ({})".format(args.scol, args.tcol, len(parts)))
                        wrong_tu_results = "c_wrong_cols"

                    # Print input sentences when scoring_only is disabled
                    if not args.score_only:
                        fileout.write("\t".join(parts) + "\t")

                    # Print scores
                    if wrong_tu_results != False:
                        fileout.write("0")
                        # Print rule annotation
                        if args.annotated_output:
                            fileout.write("\t{}\n".format(wrong_tu_results))
                        else:
                            fileout.write("\n")
                    else:
                        fileout.write("1")
                        # Print keep annotation
                        if args.annotated_output:
                            fileout.write("\tkeep\n")
                        else:
                            fileout.write("\n")

                ojob = (nblock, fileout.name)
                filein.close()
                fileout.close()


            if ojob:                    
                output_queue.put(ojob)

            os.unlink(filein_name)
        else:
            logging.debug("Exiting worker")
            break

def mapping_process(args, jobs_queue):
    logging.info("Start mapping")
    nblock = 0
    nline = 0
    mytemp = None
    for line in args.input:
        if (nline % args.block_size) == 0:
            logging.debug("Creating block {}".format(nblock))
            if mytemp:
                job = (nblock, mytemp.name)
                mytemp.close()
                jobs_queue.put(job)
                nblock += 1
            mytemp = NamedTemporaryFile(mode="w", delete=False, dir=args.tmp_dir)
            logging.debug("Mapping: creating temporary filename {0}".format(mytemp.name))
        mytemp.write(line)
        nline += 1

    if nline > 0:
        job = (nblock, mytemp.name)
        mytemp.close()        
        jobs_queue.put(job)

    return nline
        
def perform_hardrules_filtering(args):
    time_start = default_timer()
    logging.info("Starting process")
    logging.info("Running {0} workers at {1} rows per block".format(args.processes, args.block_size))

    process_count = max(1, args.processes)
    maxsize = 1000 * process_count

    output_queue = Queue(maxsize = maxsize)
    worker_count = process_count

    # Start reducer
    reduce = Process(target = reduce_process,
                     args   = (output_queue, args))
    reduce.start()

    # Start workers
    jobs_queue = Queue(maxsize = maxsize)
    workers = []
    for i in range(worker_count):
        filter = Process(target = worker_process,
                         args   = (i, jobs_queue, output_queue, args))
        filter.daemon = True # dies with the parent process

        filter.start()
        workers.append(filter)

    # Mapper process (foreground - parent)
    nline = mapping_process(args, jobs_queue)
    args.input.close()

    # Worker termination
    for _ in workers:
        jobs_queue.put(None)

    logging.info("End mapping")

    errors = False
    for w in workers:
        w.join()
        if w.exitcode != 0:
            errors = True

    # Reducer termination
    output_queue.put(None)
    reduce.join()
    

    # Stats
    logging.info("Finished")
    elapsed_time = default_timer() - time_start
    logging.info("Total: {0} rows".format(nline))
    logging.info("Elapsed time {0:.2f} s".format(elapsed_time))
    logging.info("Troughput: {0} rows/s".format(int((nline*1.0)/elapsed_time)))

    return errors

def main(args):
    logging.info("Executing main program...")
    errors = perform_hardrules_filtering(args)
    if errors:
        logging.error("Program finished with errors")
        sys.exit(1)
    else:
        logging.info("Program finished")

if __name__ == '__main__':
    try: 
        logging_setup()
        args = initialization()
        main(args)
    except Exception as ex:
        tb = traceback.format_exc()
        logging.error(tb)
        sys.exit(1)
