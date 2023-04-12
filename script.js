const currentWord = document.getElementById('current-word');
const inputWord = document.getElementById('input-word');
const scoreSpan = document.getElementById('score');
const highestScoreSpan = document.getElementById('highest-score');
const startGameBtn = document.getElementById('start-game');

let score = 0;
let highestScore = 0;
let gameInProgress = false;
let usedWords = []; // Add this line
let errorMessage = ""; // Add this line
const startingWords = [
    'apple', 'banana', 'coconut', 'dragonfruit', 'elephant', 'flamingo', 'giraffe', 'hippopotamus',
    'iguana', 'jaguar', 'kangaroo', 'lemur', 'mongoose', 'narwhal', 'octopus', 'panda',
    'quail', 'rabbit', 'seal', 'tiger'
  ];

function getRandomWord() {
    
    return startingWords[Math.floor(Math.random() * startingWords.length)];
  }
  

function startGame() {

    document.getElementById("game-over-message").style.display = "none";
    
    gameInProgress = true;
    score = 0;
    scoreSpan.textContent = score;
    currentWord.textContent = getRandomWord(); 
    inputWord.value = '';
    inputWord.focus();
    usedWords = []; // Add this line
    usedWords.push(currentWord.textContent.toLowerCase()); // Add this line
  
}



function endGame() {
    gameInProgress = false;
    if (score > highestScore) {
      highestScore = score;
      highestScoreSpan.textContent = highestScore;
    }
    document.getElementById("game-over-message").innerHTML = `Game Over! ${errorMessage}`; // Update this line
    document.getElementById("game-over-message").style.display = "block";
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
      const submitBtn = document.getElementById("submit-btn");
      submitBtn.disabled = true; // Disable the submit button
  
      const validationResult = await isValidWord(inputWord.value, currentWord.textContent);
      if (validationResult === "") {
        currentWord.textContent = inputWord.value;
        usedWords.push(inputWord.value.toLowerCase());
        score++;
        scoreSpan.textContent = score;
      } else {
        errorMessage = validationResult;
        endGame();
      }
      inputWord.value = "";
      submitBtn.disabled = false; // Enable the submit button
    }
  }
  
  

inputWord.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      submitWord();
    }
  });

inputWord.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && gameInProgress) {

    if (isValidWord(inputWord.value, currentWord.textContent)) {

      currentWord.textContent = inputWord.value;
      score++;
      scoreSpan.textContent = score;
    } else {
      endGame();
    }
    inputWord.value = '';
  }
});

window.addEventListener("load", startGame);



startGameBtn.addEventListener('click', startGame);

const submitWordBtn = document.getElementById('submit-word');

submitWordBtn.addEventListener('click', submitWord);
