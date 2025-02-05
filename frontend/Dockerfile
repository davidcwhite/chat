# Base Node image
FROM node:18-alpine AS base
WORKDIR /app

# Development stage
FROM base AS development
# Copy package files
COPY package*.json ./
# Install dependencies
RUN npm install
# Copy rest of the application
COPY . .
# Expose port
EXPOSE 3000
# Start development server
CMD ["npm", "run", "dev"]

# Production stage
FROM base AS production
# Copy package files
COPY package*.json ./
# Install production dependencies
RUN npm install --production
# Copy rest of the application
COPY . .
# Build application
RUN npm run build
# Expose port
EXPOSE 3000
# Start production server
CMD ["npm", "start"] 