

const currentWord = document.getElementById('current-word');
const inputWord = document.getElementById('input-word');
const scoreSpan = document.getElementById('score');
const highestScoreSpan = document.getElementById('highest-score');
const startGameBtn = document.getElementById('start-game');
const submitWordBtn = document.getElementById('submit-word');
const gameOverMessage = document.getElementById('game-over-message');

const timerElement = document.getElementById('timer');
let timerValue = 30;

let score = 0;
let highestScore = 0;
let gameInProgress = false;
let usedWords = [];
const startingWords = [
  'apple', 'banana', 'coconut', 'dragonfruit', 'elephant', 'flamingo', 'giraffe', 'hippopotamus',
  'iguana', 'jaguar', 'kangaroo', 'lemur', 'mongoose', 'narwhal', 'octopus', 'panda',
  'quail', 'rabbit', 'seal', 'tiger'
];

// Include the hunspell-spellchecker library
//const Spellchecker = require("hunspell-spellchecker");
//const spellchecker = new Spellchecker.default();
//const dictionary = spellchecker.dictionary("en_US");

function getRandomWord() {
  return startingWords[Math.floor(Math.random() * startingWords.length)];
}

function updateTimerDisplay() {
    timerElement.textContent = timerValue;
  }

  
function countdown() {
    if (gameInProgress && timerValue > 0) {
      timerValue--;
      updateTimerDisplay();
      if (timerValue === 0) {
        endGame('Time is up!');
      }
    }
  }
  

  function startGame() {
    gameInProgress = true;
    score = 0;
    scoreSpan.textContent = score;
    currentWord.textContent = getRandomWord();
    inputWord.value = '';
    inputWord.focus();
    usedWords = [];
    usedWords.push(currentWord.textContent.toLowerCase());
    submitWordBtn.disabled = false; // Enable the submit button
    gameOverMessage.style.display = "none";
    timerValue = 30; // Reset the timer value
    updateTimerDisplay(); // Update the timer display
    setInterval(countdown, 1000); // Start the countdown
  }
  

function endGame(reason) {
  gameInProgress = false;
  if (score > highestScore) {
    highestScore = score;
    highestScoreSpan.textContent = highestScore;
  }
  gameOverMessage.textContent = `Game Over! ${reason}`;
  gameOverMessage.style.display = "block";
  submitWordBtn.disabled = true; // Disable the submit button
}

async function isValidWord(word, prevWord) {
    const isRepeatingChar = (word) => {
      for (let i = 1; i < word.length; i++) {
        if (word[i].toLowerCase() !== word[i - 1].toLowerCase()) {
          return false;
        }
      }
      return true;
    };
  
    if (word.length === 0) {
      return "Please enter a word.";
    }
    if (isRepeatingChar(word)) {
      return "Invalid word: consecutive repeating characters are not allowed.";
    }
    if (usedWords.includes(word.toLowerCase())) {
      return "Invalid word: you have already used this word.";
    }
    if (word[0].toLowerCase() !== prevWord[prevWord.length - 1].toLowerCase()) {
      return "Invalid word: the word should start with the last letter of the previous word.";
    }
  
    const response = await fetch(
      `https://api.datamuse.com/words?sp=${word.toLowerCase()}&max=1`
    );
    const data = await response.json();
  
    if (data.length === 0 || data[0].word.toLowerCase() !== word.toLowerCase()) {
      return "Invalid word: the word is not recognized.";
    }
  
    return "";
  }

  async function submitWord() {
    if (gameInProgress) {
      const word = inputWord.value.trim();
      const prevWord = currentWord.textContent.trim();
      const validationResult = await isValidWord(word, prevWord);
  
      if (validationResult === "") {
        currentWord.textContent = word;
        usedWords.push(word.toLowerCase());
        score++;
        scoreSpan.textContent = score;
      } else {
        endGame(validationResult);
      }
      inputWord.value = "";
      inputWord.focus();
    }
  }

inputWord.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    submitWord();
  }
});

startGameBtn.addEventListener('click', startGame);
submitWordBtn.addEventListener('click', submitWord);

// Start the game on page load
window.addEventListener("load", startGame);


