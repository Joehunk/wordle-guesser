#!/usr/bin/env python3
from collections.abc import Iterable
from enum import Enum
import operator
from joblib import Parallel, delayed
import re

class LetterColor(Enum):
    GREEN = 1
    YELLOW = 2
    BLACK = 3
    UNDEFINED = 0

def findYellowAndGreenMatches(hiddenWord, candidateWord):
    if len(hiddenWord) != len(candidateWord):
        raise RuntimeError("Compared words must be same length")

    greenMatches = 0
    yellowMatches = 0
    unmatchedLettersInHiddenWord = list(hiddenWord)
    unmatchedLettersInCandidateWord = list(candidateWord)
    for i in range(len(candidateWord)):
        if candidateWord[i] == hiddenWord[i]:
            greenMatches += 1
            unmatchedLettersInHiddenWord.remove(hiddenWord[i])
            unmatchedLettersInCandidateWord.remove(candidateWord[i])

    for unmatchedCandidateLetter in unmatchedLettersInCandidateWord:
        if unmatchedCandidateLetter in unmatchedLettersInHiddenWord:
            yellowMatches += 1
            unmatchedLettersInHiddenWord.remove(unmatchedCandidateLetter)

    if yellowMatches + greenMatches > len(candidateWord):
        raise RuntimeError("There be bugs here: " + repr((yellowMatches, greenMatches)))
    return (yellowMatches, greenMatches)
                
class WordScore:
    def __init__(self, word: str):
        self.word = word
        
        # Index zero will equal "number of words with zero yellow matches to this word" and
        # so on. We keep it in an array so we can calculate medians.
        self.yellowMatches = [0] * 6
        self.greenMatches = [0] * 6
    
    def recordMatch(self, otherWord: str):
        if self.word == otherWord:
            return
        (yellowMatches, greenMatches) = findYellowAndGreenMatches(otherWord, self.word)
        self.greenMatches[greenMatches] += 1
        self.yellowMatches[yellowMatches] += 1
        
    def getTotalGreenMatches(self):
        return sum([ i*j for i, j in zip(self.greenMatches, range(6)) ])

    def getTotalYellowMatches(self):
        return sum([ i*j for i, j in zip(self.yellowMatches, range(6)) ])

def readWordsFromRawTextFile(f) -> Iterable[str]:
    return f.readlines()

def readWordsFromWordnetIndexFile(f) -> Iterable[str]:
    return [ line.split()[0] for line in f.readlines() if len(line) ]

def normalizeWord(word: str) -> str:
    return word.strip().lower()

fiveLetterWordRegex = re.compile("^[a-z]{5}$")

def isFiveLetterWord(word: str) -> bool:
    return fiveLetterWordRegex.fullmatch(word) and True or False

def getAllFiveLetterWordsFromFile(f, reader=readWordsFromRawTextFile):
    normalizedWords = map(normalizeWord, reader(f))
    return filter(isFiveLetterWord, normalizedWords)

# Change this to change how words are scored.
def computeWeightedScore(score: WordScore) -> float:
    return float(score.getTotalGreenMatches()) + float(score.getTotalYellowMatches())
    
def noLettersInCommon(word1, word2):
    for letter in word1:
        if letter in word2:
            return False
    return True
 
def findBestWordleFirstGuess(allWordsDictionary: str, nounsDictionary: str):
    possibleGuesses = []
    possibleAnswers = []
    with open(allWordsDictionary) as dictionaryFile:
        possibleGuesses = list(getAllFiveLetterWordsFromFile(dictionaryFile))
        
    with open(nounsDictionary) as dictionaryFile:
        possibleAnswers = list(getAllFiveLetterWordsFromFile(dictionaryFile, reader=readWordsFromWordnetIndexFile))
    
    def recordAllMatches(word):
        nonlocal possibleAnswers
        wordScore = WordScore(word)
        for word in possibleAnswers:
                wordScore.recordMatch(word)
        return wordScore
        
    wordScores = Parallel(n_jobs = 8)(delayed(recordAllMatches)(word) for word in possibleGuesses)
    bestWord = max(wordScores, key=computeWeightedScore)
    print("The best word is: " + bestWord.word)
    print("Green match histogram: " + repr(bestWord.greenMatches))
    print("Yellow match histogram: " + repr(bestWord.yellowMatches))
    
    wordsWithNoLettersInCommonWithBestWord = list(filter(lambda x: noLettersInCommon(bestWord.word, x.word), wordScores))
    
    if not wordsWithNoLettersInCommonWithBestWord:
        print("There is no next best word UR screwed")
    else:
        nextBestWord = max(wordsWithNoLettersInCommonWithBestWord, key=computeWeightedScore)
        print("The next best word is: " + nextBestWord.word)
        print("Green match histogram: " + repr(nextBestWord.greenMatches))
        print("Yellow match histogram: " + repr(nextBestWord.yellowMatches))
        
def getTopTenLetters(nounsDictionary, reader):
    possibleAnswers = []
    letterCount = {}
    with open(nounsDictionary) as dictionaryFile:
        possibleAnswers = list(getAllFiveLetterWordsFromFile(dictionaryFile, reader=reader))
    
    for word in possibleAnswers:
        uniqueLetters = set(word)
        for letter in uniqueLetters:
            letterCount[letter] = letterCount.setdefault(letter, 0) + 1
            
    countsAndLetters = [ (count, letter) for letter, count in letterCount.items() ]
    countsAndLetters.sort()
    countsAndLetters.reverse()
    return [ letter for count, letter in countsAndLetters[:10] ]

def getWordPairWithMostCommonLetters(allWordsDictionary: str, nounsDictionary: str):
    possibleGuesses = []
    with open(allWordsDictionary) as dictionaryFile:
        possibleGuesses = list(getAllFiveLetterWordsFromFile(dictionaryFile))
        
    topTenLetters = set(getTopTenLetters(nounsDictionary, readWordsFromWordnetIndexFile))
    def hasAllUniqueTopTenLetters(word: str) -> bool:
        nonlocal topTenLetters
        if len(set(word)) != 5:
            return False # This means some letters are repeated.
        for letter in word:
            if not letter in topTenLetters:
                return False
        return True
    
    wordsWithTopTenLetters = list(filter(hasAllUniqueTopTenLetters, possibleGuesses))
    
    def findOtherTopTenWordWithNoLettersInCommon(word: str) -> Iterable[str]:
        nonlocal wordsWithTopTenLetters
        pairWords = []
        lettersInThisWord = set(word)
        for possiblePairWord in wordsWithTopTenLetters:
            lettersInCommonBetweenBothWords = False
            for letter in possiblePairWord:
                if letter in lettersInThisWord:
                    lettersInCommonBetweenBothWords = True
                    break
            
            if not lettersInCommonBetweenBothWords and \
                possiblePairWord != word and hasAllUniqueTopTenLetters(possiblePairWord):
                pairWords.append(possiblePairWord)
        return word, pairWords
    
    wordsAndPossiblePairs = Parallel(n_jobs = 8)(delayed(findOtherTopTenWordWithNoLettersInCommon)(word) for word in wordsWithTopTenLetters)
    pairs = set()
    for word, pairedWords in wordsAndPossiblePairs:
        for pairedWord in pairedWords:
            pair = [ word, pairedWord ]
            pair.sort()
            pairs.add(tuple(pair))
    return pairs

def colorWord(hiddenAnswer: str, guess: str):
    if len(hiddenAnswer) != len(guess):
        raise RuntimeError("Unequal length guess vs. word")
    lettersAndColors = [ None ] * len(hiddenAnswer)
    unmatchedLettersFromGuess = list(guess)
    for i in range(len(hiddenAnswer)):
        if hiddenAnswer[i] == guess[i]:
            unmatchedLettersFromGuess.remove(hiddenAnswer[i])
            lettersAndColors[i] = (guess[i], LetterColor.GREEN)
    for i in range(len(hiddenAnswer)):
        if lettersAndColors[i]:
            continue
        if hiddenAnswer[i] in unmatchedLettersFromGuess:
            unmatchedLettersFromGuess.remove(hiddenAnswer[i])
            lettersAndColors[i] = (guess[i], LetterColor.YELLOW)
        else:
            lettersAndColors[i] = (guess[i], LetterColor.BLACK)
    return lettersAndColors
        
def isWordEliminatedByGuess(hiddenAnswer: str, wordToEliminate: str, guess: str) -> bool:
    guessLettersAndColors = colorWord(hiddenAnswer, guess)
    unmatchedLettersInWordToEliminate = list(wordToEliminate)
    for i in range(len(guessLettersAndColors)):
        guessLetter, guessColor = guessLettersAndColors[i]
        if guessColor == LetterColor.GREEN and wordToEliminate[i] != guessLetter:
            return True
        elif guessColor == LetterColor.YELLOW:
            if wordToEliminate[i] == guessLetter:
                return True
            if not guessLetter in unmatchedLettersInWordToEliminate:
                return True
            unmatchedLettersInWordToEliminate.remove(guessLetter)
        elif guessColor == LetterColor.BLACK:
            if guessLetter in wordToEliminate:
                return True
    return False
    
def isWordEliminatedByGuesses(hiddenAnswer: str, wordToEliminate: str, previousGuesses: Iterable[str]) -> bool:
    if not len(previousGuesses):
        return False
    return isWordEliminatedByGuess(hiddenAnswer, wordToEliminate, previousGuesses[0]) or \
        isWordEliminatedByGuesses(hiddenAnswer, wordToEliminate, previousGuesses[1:])
        
def getPossibleAnswersGivenGuessesSoFar(hiddenAnswer: str, possibleAnswers: Iterable[str], guessesSoFar: Iterable[str]) -> Iterable[str]:
    def isPossible(guess):
        nonlocal hiddenAnswer, guessesSoFar
        return not isWordEliminatedByGuesses(hiddenAnswer, guess, guessesSoFar)
    return filter(isPossible, possibleAnswers)
        
def getLetterWordPairsSortedByMostEliminatedWordCount(allWordsDictionary: str, nounsDictionary: str):
    # TODO refactor to allow passing of filename, open file, or collection.
    possibleAnswers = []
    with open(nounsDictionary) as dictionaryFile:
        possibleAnswers = list(getAllFiveLetterWordsFromFile(dictionaryFile, reader=readWordsFromWordnetIndexFile))
        
    pairs = list(getWordPairWithMostCommonLetters(allWordsDictionary, nounsDictionary))
    
    def scorePairByMostEliminatedWords(wordPair):
        nonlocal possibleAnswers
        eliminatedWords = 0
        for hiddenAnswer in possibleAnswers:
            for wordToEliminate in possibleAnswers:
                if isWordEliminatedByGuesses(hiddenAnswer, wordToEliminate, wordPair):
                    eliminatedWords += 1
        return (eliminatedWords, wordPair[0], wordPair[1])
    
    scoredPairs = Parallel(n_jobs = 8)(delayed(scorePairByMostEliminatedWords)(wordPair) for wordPair in pairs)
    scoredPairs.sort()
    scoredPairs.reverse()
    return scoredPairs

if __name__ == "__main__":
    import sys
    pairs = getLetterWordPairsSortedByMostEliminatedWordCount(sys.argv[1], sys.argv[2])
    for pair in pairs[:100]:
        print(pair)
    