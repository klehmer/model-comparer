FROM node:18-alpine

WORKDIR /app

# Set environment variables to prevent thread creation issues
ENV NODE_OPTIONS="--max-old-space-size=4096"
ENV NPM_CONFIG_PREFER_OFFLINE=true
ENV NPM_CONFIG_CACHE=/tmp/npm-cache

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies with specific flags to avoid thread issues
RUN npm install --only=production --no-audit --no-fund --prefer-offline --foreground-scripts --jobs=1

# Copy application code
COPY . .

# Expose port if needed
EXPOSE 3000

CMD ["node", "app.js"]
