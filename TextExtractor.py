import argparse
import datetime
import logging
from os import listdir
from os.path import isfile, join
import pytesseract
import re
import requests
from unidecode import unidecode

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


# Returns the valid text contained in a locally-stored image. Valid text
# is text that's an english word, or colloquial slang.
class TextExtractor(object):
    def __init__(self, englishChecker, slangChecker):
        self.englishChecker = englishChecker
        self.slangChecker = slangChecker

    def getAllText(self, path):
        return pytesseract.image_to_string(path)

    def getSanitizedTokens(self, text):
        tokens = list()
        for tok in text.split():
            t = self.sanitizeToken(tok)
            if t:
                tokens.append(t)
        return tokens

    # Convert to unicode, make lower-case, remove non-alphabetical characters,
    # and remove trailing newlines.
    def sanitizeToken(self, token):
        uni = unidecode(token)
        lo = uni.lower()
        return re.sub("[^a-zA-Z-]", "", lo)

    def getValidText(self, path):
        valid_words = list()
        invalid_words = list()

        all_text = self.getAllText(path)
        sanitized_tokens = self.getSanitizedTokens(all_text)
        for token in sanitized_tokens:
            if self.englishChecker.isValid(token) or self.slangChecker.isValid(
                    token):
                valid_words.append(token)
            else:
                invalid_words.append(token)

        logging.info("Image {} had valid words {} and invalid words {}".format(
            path, valid_words, invalid_words))
        return valid_words


class SlangChecker(object):
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def isValid(self, token):
        response = requests.get(self.endpoint.format(token))
        logging.info("SlangChecker endpoint returned {} for token '{}'".format(
            response.status_code, token))
        return response.status_code == requests.codes['ok']


class EnglishDictionary(object):
    def __init__(self, word_files):
        self.words = dict()
        for wf in word_files:
            self.addWordsFromFile(wf)

    def sanitizeWord(self, word):
        return word.lower().rstrip()

    def addWordsFromFile(self, path):
        words_added = 0
        with open(path, 'r') as f:
            for word in f:
                sanitizedWord = self.sanitizeWord(word)
                if sanitizedWord not in self.words:
                    self.words[sanitizedWord] = True
                    words_added += 1
        f.close()
        logging.info(
            "Added {} valid words to dictionary. Current size: {}".format(
                words_added, len(self.words)))

    def isValid(self, token):
        return token in self.words


# Hash file names, sizes, and collected data.
def getOutputPath(data, outputPath):
    return datetime.datetime.today().strftime('%Y-%m-%d_%H:%M:%S') + '_' + str(
        len(data)) + '.txt'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Extract valid words from input memes')
    parser.add_argument(
        '--input_data_path',
        help='directory from which to read input memes',
        default='training_memes')
    parser.add_argument(
        '--output_data_path',
        help='directory to which to write extracted text',
        default='training_text')
    parser.add_argument(
        '--word_sources',
        help='sources from which to build the english dictionary',
        default='/usr/share/dict/words,resources/popular_words.txt')
    parser.add_argument(
        '--urban_dictionary_endpoint_template',
        help='',
        default='https://www.urbandictionary.com/define.php?term={}')
    args = parser.parse_args()

    englishDictionary = EnglishDictionary(args.word_sources.split(','))
    slangChecker = SlangChecker(args.urban_dictionary_endpoint_template)
    extractor = TextExtractor(englishDictionary, slangChecker)

    photos_to_process = [
        f for f in listdir(args.input_data_path)
        if isfile(join(args.input_data_path, f))
    ]
    logging.info(
        "Processing the following photos: {}".format(photos_to_process))

    results = list()
    for photo in photos_to_process:
        valid_text = extractor.getValidText(join(args.input_data_path, photo))
        results.append(valid_text)
        logging.info("Processed photo '{}' and got {}".format(
            photo, valid_text))

    outputFilePath = getOutputPath(results, args.output_data_path)
    with open(join(args.output_data_path, outputFilePath), 'w') as f:
        for wordList in results:
            f.write(' '.join(wordList) + '\n')
    f.close()
    logging.info("Extracted {} memes and wrote to file '{}'".format(
        len(results), outputFilePath))
