const currentWord = document.getElementById('current-word');
const inputWord = document.getElementById('input-word');
const scoreSpan = document.getElementById('score');
const highestScoreSpan = document.getElementById('highest-score');
const startGameBtn = document.getElementById('start-game');

let score = 0;
let highestScore = 0;
let gameInProgress = false;

function startGame() {
    const startingWords = [
      'apple', 'banana', 'coconut', 'dragonfruit', 'elephant', 'flamingo', 'giraffe', 'hippopotamus',
      'iguana', 'jaguar', 'kangaroo', 'lemur', 'mongoose', 'narwhal', 'octopus', 'panda',
      'quail', 'rabbit', 'seal', 'tiger'
    ];
    
    gameInProgress = true;
    score = 0;
    scoreSpan.textContent = score;
    currentWord.textContent = startingWords[Math.floor(Math.random() * startingWords.length)];
    inputWord.value = '';
    inputWord.focus();
}

function endGame() {
  gameInProgress = false;
  if (score > highestScore) {
    highestScore = score;
    highestScoreSpan.textContent = highestScore;
  }
}

function isValidWord(word, prevWord) {
 
  return word.length > 0 && word[0].toLowerCase() === prevWord[prevWord.length - 1].toLowerCase();
}

inputWord.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      submitWord();
    }
  });

inputWord.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && gameInProgress) {
    console.log('before is valid world');
    if (isValidWord(inputWord.value, currentWord.textContent)) {
        console.log('is valid world');
      currentWord.textContent = inputWord.value;
      score++;
      scoreSpan.textContent = score;
    } else {
      endGame();
    }
    inputWord.value = '';
  }
});


function submitWord() {
    if (gameInProgress) {
      if (isValidWord(inputWord.value, currentWord.textContent)) {
        currentWord.textContent = inputWord.value;
        score++;
        scoreSpan.textContent = score;
      } else {
        endGame();
      }
      inputWord.value = '';
    }
  }

startGameBtn.addEventListener('click', startGame);

const submitWordBtn = document.getElementById('submit-word');

submitWordBtn.addEventListener('click', submitWord);
