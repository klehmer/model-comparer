const express = require('express');
const path = require('path');
const axios = require('axios');
const app = express();
const port = 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Serve static HTML
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'index.html'));
});

// Handle form submit
app.post('/submit', async (req, res) => {
  const textInput = req.body.text;
  const model = req.body.model || 'llama3';

  try {
    const response = await axios.post('http://backend:5000/api/submit', {
      text: textInput,
      model: model
    });
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.response?.data?.error || 'Unknown error' });
  }
});

// Proxy route to get texts from backend
app.get('/api/texts', async (req, res) => {
  try {
    const response = await axios.get('http://backend:5000/api/texts');
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.response?.data?.error || 'Unknown error' });
  }
});

// Proxy route to delete all texts from backend
app.delete('/api/texts', async (req, res) => {
  try {
    const response = await axios.delete('http://backend:5000/api/texts');
    res.status(response.status).json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.response?.data?.error || 'Unknown error' });
  }
});

// Proxy route to delete a single text by ID
app.delete('/api/texts/:id', async (req, res) => {
  try {
    const response = await axios.delete(`http://backend:5000/api/texts/${req.params.id}`);
    res.status(response.status).json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.response?.data?.error || 'Unknown error' });
  }
});

// Proxy route to stream GPT response from backend
app.post('/api/stream_gpt', async (req, res) => {
  try {
    const response = await axios({
      method: 'post',
      url: 'http://backend:5000/api/stream_gpt',
      data: req.body,
      responseType: 'stream',
      headers: { 'Content-Type': 'application/json' }
    });
    res.setHeader('Content-Type', 'text/event-stream');
    response.data.pipe(res);
  } catch (error) {
    res.status(500).json({ error: error.response?.data?.error || 'Unknown error' });
  }
});

app.listen(port, () => {
  console.log(`Frontend running at http://localhost:${port}`);
});
