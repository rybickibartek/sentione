from nltk import word_tokenize, sent_tokenize
import json
import requests

def getLink(tokenized_sent):
    # pobieranie tokenów razem z tagami w formie JSON'a
    return 'http://clarin.pelcra.pl/tools/api/tagger/tag?text=' + '%20'.join(tokenized_sent) + '%20&tagger=openNLP&tagset=standard&format=JSON&lang=pl'

def getHalfTokens(tokenized_sent):
    # wyłuskiwanie tokenów i tagów z JSON'a
    json_data = json.loads(requests.get(getLink(tokenized_sent)).text)
    return [(json_data[0][i]['orth'], json_data[0][i]['lexes'][0]['alias']) for i in range(len(json_data[0]))]

def pos_tag(tokenized_sent):
    # składanie słów z ich fragmentów które odebraliśmy w JSON'ie
    halftoken_pos = getHalfTokens(tokenized_sent)

    index = -1
    result = []
    for token in tokenized_sent:
        index += 1
        word = halftoken_pos[index][0]
        pos = halftoken_pos[index][1]
        while token != word:
            index += 1
            word += halftoken_pos[index][0]
        result.append((token, pos))

    return result

def differentCharacterThenPreviousOne(char, sentence):
    # sprawdzanie czy znak jest inny niż ostatnio dodany
    if len(sentence) == 0:
        return True
    else:
        return char != sentence[-1]

def makeSentenceClean(sentence):
    # wyrzucanie ze zdania znaków których nie chcemy wysyłać do otagowania
    cleanSentence = []
    nonAlphaCharacters = []
    indexes = []
    for index, char in enumerate(sentence):
        if char == ' ' or char.isalpha() or char.isdigit() or (char in [',', '.'] and differentCharacterThenPreviousOne(char, cleanSentence)):
            cleanSentence.append(char)
        else:
            indexes.append(index)
            nonAlphaCharacters.append(char)

    return ''.join(cleanSentence), nonAlphaCharacters, indexes

def howManyVerbsSentenceContains(sentence):
    # zliczanie czasowników w zdaniu
    count = 0
    for (word, pos) in sentence:
        if pos == 'verb':
            count += 1
    return count

def containsVerb(sentence):
    # określanie czy zdanie zawiera choć jeden czasownik
    return howManyVerbsSentenceContains(sentence) > 0

def cutAfterVerbs(sentence, verbsCount):
    # cięcie kandydatów na zdania proste, którzy zawierają więcej niż jeden czasownik na zdania proste
    sentences = [[]]
    cuts = 0
    for (word, pos) in sentence:
        sentences[-1].append((word, pos))
        if pos == 'verb' and cuts < verbsCount - 1:
            sentences.append([])
            cuts += 1

    if sentences[-1] == []:
        sentences = sentences[:-1]
    return sentences

def solveProblemWithMoreThanOneVerb(partition):
    # wybranie zdań kandydatów, którzy mają więcej niż jeden czasownik i rozwiązanie tego problemu
    simpleSentences = []
    for sentence in partition:
        verbsCount = howManyVerbsSentenceContains(sentence)
        if verbsCount > 1:
            simpleSentences.extend(cutAfterVerbs(sentence, verbsCount))
        else:
            simpleSentences.append(sentence)
    return simpleSentences

def improvePartitioning(partition):
    # jeśli w wyniku dzielenia po spójniku powstały zdania które nie mają orzeczenia to trzeba je skleić z jakimś zdaniem sąsiednim
    improvedPartition = [partition[0]]
    for simpleSentence in partition[1:]:
        if containsVerb(simpleSentence) and containsVerb(improvedPartition[-1]):
            improvedPartition.append(simpleSentence)
        else:
            improvedPartition[-1].extend(simpleSentence)

    for i, simpleSentence in enumerate(improvedPartition):
        if simpleSentence[-1][1] == 'conj':
            improvedPartition[i] = simpleSentence[:-1]

    improvedPartition = solveProblemWithMoreThanOneVerb(improvedPartition)

    return improvedPartition

def addNonAlphaIfPossible(token, inputedNonAlpha, indexesOfNonAlphaCharacters, nonAlphaCharacters, charSeen):
    # wstaw znak nonAlpha na jego miejsce
    if inputedNonAlpha < len(indexesOfNonAlphaCharacters) and charSeen + inputedNonAlpha == indexesOfNonAlphaCharacters[inputedNonAlpha]:
        token += nonAlphaCharacters[inputedNonAlpha]
        inputedNonAlpha += 1
    return token, inputedNonAlpha

def inputNonAlphaAndFixHashtagPOS(word_pos, nonAlphaCharacters, indexesOfNonAlphaCharacters):
    # wstawianie usniętych znaków nonAlpha
    inputedNonAlpha = 0
    charSeen = 0
    fullText = []
    for (word, pos) in word_pos:
        token = ''
        for ch in word:
            token, inputedNonAlpha = addNonAlphaIfPossible(token, inputedNonAlpha, indexesOfNonAlphaCharacters, nonAlphaCharacters, charSeen)
            charSeen += 1
            token += ch
        token, inputedNonAlpha = addNonAlphaIfPossible(token, inputedNonAlpha, indexesOfNonAlphaCharacters, nonAlphaCharacters, charSeen)
        fullText.append((token, pos))
        charSeen += 1
    if inputedNonAlpha < len(indexesOfNonAlphaCharacters):
        fullText[-1] = (fullText[-1][0] + ''.join(nonAlphaCharacters[(inputedNonAlpha - len(indexesOfNonAlphaCharacters)):]), fullText[-1][1])

    # słowo będące hashtagiem to rzeczownik i koniec ;-)
    output = []
    for (word, pos) in fullText:
        if word[0] == '#' and len(word) > 1:
            output.append((word, 'noun'))
        else:
            output.append((word, pos))
    return output

def splitComplexSentenceOnSimpleSentences(sentence):
    # podział zdania złożonego na zdanie proste
    cleanSentence, nonAlphaCharacters, indexesOfNonAlphaCharacters = makeSentenceClean(sentence)
    word_pos = pos_tag(word_tokenize(cleanSentence))
    complete_word_pos = inputNonAlphaAndFixHashtagPOS(word_pos, nonAlphaCharacters, indexesOfNonAlphaCharacters)

    sents = [[]]
    for (word, pos) in complete_word_pos:
        sents[-1].append((word, pos))
        if pos == 'conj':
            sents.append([])

    result = []
    for simpleSentence in improvePartitioning(sents):
        result.append(' '.join([word for (word, _) in simpleSentence]))

    return result

example = input()

result = []
for sentence in sent_tokenize(example.replace('\n', ' ')):
    result.extend(splitComplexSentenceOnSimpleSentences(sentence))
print()
print(' | '.join(result))
print()