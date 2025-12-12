# UI Dockerfile for Agentic Exception Processing Platform
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code (will be overridden by volume mounts in development)
COPY . .

# Expose port
EXPOSE 3000

# Start development server with host binding for Docker
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
