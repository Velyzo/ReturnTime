const popupButton = document.getElementById('popupButton');
const discordPopup = document.getElementById('discordPopup');
const closePopup = document.getElementById('closePopup');

popupButton.addEventListener('click', () => {
  discordPopup.style.display = 'block';
});

closePopup.addEventListener('click', () => {
  discordPopup.style.display = 'none';
});