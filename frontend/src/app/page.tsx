'use client'
import { useState, useRef, useEffect } from 'react'
import Image from 'next/image'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import remarkGfm from 'remark-gfm'

export default function Home() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setSidebarOpen] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini')
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const smoothScrollToBottom = () => {
    if (!messagesEndRef.current) return;

    const scrollContainer = messagesEndRef.current.parentElement;
    if (!scrollContainer) return;

    const targetScrollTop = scrollContainer.scrollHeight - scrollContainer.clientHeight;
    const startScrollTop = scrollContainer.scrollTop;
    const distance = targetScrollTop - startScrollTop;
    
    if (distance <= 0) return; // Don't scroll if we're already at the bottom

    const duration = 100; // milliseconds - adjust this for faster/slower scroll
    const startTime = performance.now();

    const animateScroll = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function for smooth deceleration
      const easeOutCubic = (x: number) => 1 - Math.pow(1 - x, 3);
      const easedProgress = easeOutCubic(progress);

      scrollContainer.scrollTop = startScrollTop + (distance * easedProgress);

      if (progress < 1) {
        requestAnimationFrame(animateScroll);
      }
    };

    requestAnimationFrame(animateScroll);
  }

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      smoothScrollToBottom();
    }
  }

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Check if we're near bottom (within 100px)
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      
      // Enable auto-scroll if user has scrolled to bottom
      if (isNearBottom) {
        setAutoScroll(true);
      } else {
        // Disable auto-scroll if user has scrolled up
        setAutoScroll(false);
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (autoScroll) {
      const timeoutId = setTimeout(() => {
        scrollToBottom();
      }, 10);
      return () => clearTimeout(timeoutId);
    }
  }, [messages, currentStreamingMessage, autoScroll]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    setIsLoading(true)
    const newMessages = [...messages, { role: 'user', content: input }]
    setMessages(newMessages)
    setInput('')
    setCurrentStreamingMessage('')

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: input,
          model: selectedModel 
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullMessage = ''

      if (!reader) {
        throw new Error('No reader available')
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(5))
              if (data.content) {
                fullMessage += data.content
                setCurrentStreamingMessage(fullMessage)
              }
            } catch (error) {
              console.error('Error parsing chunk:', error)
            }
          }
        }
      }

      // After streaming is complete, add the full message to the messages array
      setMessages(prev => [...prev, { role: 'assistant', content: fullMessage }])
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
      setCurrentStreamingMessage('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // Could add toast notification here
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const MarkdownComponent = ({ content }: { content: string }) => (
    <ReactMarkdown
      className="prose prose-sm lg:prose-base max-w-none prose-pre:p-0 prose-pre:m-0 prose-pre:bg-transparent"
      remarkPlugins={[remarkGfm]}
      components={{
        // Headers
        h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4" {...props}/>,
        h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-5 mb-3" {...props}/>,
        h3: ({node, ...props}) => <h3 className="text-lg font-bold mt-4 mb-2" {...props}/>,
        
        // Code blocks
        code: ({node, inline, className, children, ...props}) => {
          const match = /language-(\w+)/.exec(className || '')
          
          if (!inline && match) {
            // This is a code block
            return (
              <SyntaxHighlighter
                language={match[1]}
                style={oneLight}
                PreTag="div"
                customStyle={{
                  margin: '1em 0',
                  borderRadius: '0.5rem',
                  padding: '1em',
                }}
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            )
          }
          
          // This is inline code
          return (
            <code
              className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800"
              {...props}
            >
              {children}
            </code>
          )
        },
        
        // Blockquotes
        blockquote: ({node, ...props}) => (
          <blockquote className="border-l-4 border-gray-200 pl-4 my-4 italic" {...props}/>
        ),
        
        // Lists
        ul: ({node, ...props}) => <ul className="list-disc list-inside my-4" {...props}/>,
        ol: ({node, ...props}) => <ol className="list-decimal list-inside my-4" {...props}/>,
        
        // Links
        a: ({node, ...props}) => (
          <a className="text-blue-500 hover:text-blue-600 underline" {...props}/>
        ),
        
        // Tables
        table: ({node, ...props}) => (
          <div className="overflow-x-auto my-4">
            <table className="min-w-full table-auto border-collapse" {...props}/>
          </div>
        ),
        th: ({node, ...props}) => (
          <th className="border border-gray-300 px-4 py-2 bg-gray-50" {...props}/>
        ),
        td: ({node, ...props}) => (
          <td className="border border-gray-300 px-4 py-2" {...props}/>
        ),
        p: ({node, ...props}) => <p className="my-3 leading-relaxed" {...props}/>,
      }}
    >
      {content}
    </ReactMarkdown>
  )

  const ModelSelector = () => (
    <div className="absolute left-0 top-0 w-full bg-gray-100 z-20 h-16 flex items-center px-8">
      <div className="relative inline-block">
        <button
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50/50 rounded-md bg-gray-100"
          onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
        >
          <span className="font-medium">
            {selectedModel === 'o3-mini' ? 'ChatGPT o3-mini' : 'ChatGPT gpt-4o-mini'}
          </span>
          <svg className="w-4 h-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        
        {isModelDropdownOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setIsModelDropdownOpen(false)} />
            
            <div className="absolute left-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-30">
              <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-100">
                Select a model
              </div>
              
              {/* o3-mini Option */}
              <div 
                className="px-4 py-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => {
                  setSelectedModel('o3-mini')
                  setIsModelDropdownOpen(false)
                }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-medium text-sm">ChatGPT o3-mini</div>
                    <div className="text-xs text-gray-500">Most capable model, better at complex tasks</div>
                  </div>
                  {selectedModel === 'o3-mini' && (
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </div>
              
              {/* gpt-4o-mini Option */}
              <div 
                className="px-4 py-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => {
                  setSelectedModel('gpt-4o-mini')
                  setIsModelDropdownOpen(false)
                }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-medium text-sm">ChatGPT gpt-4o-mini</div>
                    <div className="text-xs text-gray-500">Faster responses, more concise</div>
                  </div>
                  {selectedModel === 'gpt-4o-mini' && (
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div 
        className={`fixed md:static h-full bg-gray-900 text-white transition-all duration-300 ease-in-out z-10 ${
          isSidebarOpen ? 'w-64' : 'w-0 md:w-16'
        }`}
      >
        <div className="flex items-center h-16 px-4">
          <div className="flex-1 flex justify-center">
            <div className="flex items-center">
              <Image
                src="/images/logoipsum-logo-1-1.png"
                alt="Logo"
                width={150}
                height={52}
                className={`${!isSidebarOpen && 'md:hidden'}`}
              />
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(!isSidebarOpen)}
            className="text-white hover:text-gray-300 transition-colors"
          >
            {isSidebarOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
        
        <div className={`${!isSidebarOpen && 'md:hidden'}`}>
          <div className="px-4 py-8 flex justify-center">
            <button 
              onClick={() => setMessages([])} 
              className="px-6 py-2 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
            >
              New Chat
            </button>
          </div>
          <div className="border-t border-gray-700 mx-4">
            <div className="text-sm text-gray-400 pt-8">Previous chats</div>
          </div>
        </div>
      </div>

      {/* Overlay for mobile */}
      {isSidebarOpen && (
        <div 
          className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-0"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col relative">
        <ModelSelector />
        
        {/* Mobile menu button */}
        <button
          onClick={() => setSidebarOpen(true)}
          className={`md:hidden absolute top-4 left-4 z-30 p-2 rounded-lg bg-gray-900 text-white ${
            isSidebarOpen ? 'hidden' : 'block'
          }`}
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div 
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto pt-16 px-8 pb-4 space-y-6"
        >
          {messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === 'user' ? 'justify-end mr-4' : 'justify-start ml-4'}`}>
              <div className={`relative px-4 py-2 max-w-[70%] ${
                message.role === 'user' 
                  ? 'bg-white shadow border border-gray-100 rounded-lg'
                  : 'text-gray-900'
              }`}>
                {message.role === 'assistant' ? (
                  <>
                    <MarkdownComponent content={message.content} />
                    <div className="flex justify-start mt-2">
                      <button
                        onClick={() => copyToClipboard(message.content)}
                        className="p-1.5 text-gray-500 hover:text-purple-500 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Copy to clipboard"
                      >
                        <svg 
                          className="w-5 h-5" 
                          viewBox="0 0 24 24" 
                          fill="none" 
                          stroke="currentColor" 
                          strokeWidth="2" 
                          strokeLinecap="round" 
                          strokeLinejoin="round"
                        >
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                      </button>
                    </div>
                  </>
                ) : (
                  message.content
                )}
              </div>
            </div>
          ))}
          
          {currentStreamingMessage && (
            <div className="flex justify-start ml-4">
              <div className="relative px-4 py-2 max-w-[70%] text-gray-900">
                <MarkdownComponent content={currentStreamingMessage} />
                <div className="flex justify-start mt-2">
                  <button
                    onClick={() => copyToClipboard(currentStreamingMessage)}
                    className="p-1.5 text-gray-500 hover:text-purple-500 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Copy to clipboard"
                  >
                    <svg 
                      className="w-5 h-5" 
                      viewBox="0 0 24 24" 
                      fill="none" 
                      stroke="currentColor" 
                      strokeWidth="2" 
                      strokeLinecap="round" 
                      strokeLinejoin="round"
                    >
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          )}
          
          {isLoading && !currentStreamingMessage && (
            <div className="flex justify-start ml-4">
              <div className="px-4 py-2 text-gray-900">
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Updated Input form */}
        <div className="p-4 bg-gray-100">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200">
              {/* Message input area */}
              <div className="flex gap-4 p-2">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="flex-1 resize-none p-2 focus:outline-none"
                  placeholder="How can I help?"
                  style={{ maxHeight: '200px', minHeight: '24px' }}
                />
                <button 
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="self-end px-4 py-2 bg-purple-400 text-white rounded-lg hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M20 12L4 4L6 12L4 20L20 12Z" fill="currentColor" />
                  </svg>
                </button>
              </div>

              {/* Tools bar */}
              <div className="border-t border-gray-100 p-2 flex items-center justify-between">
                <div className="flex gap-2">
                  {/* Document upload */}
                  <button
                    type="button"
                    className="p-2 text-gray-500 hover:text-purple-500 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Upload files"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                  </button>

                  {/* Web search */}
                  <button
                    type="button"
                    className="p-2 text-gray-500 hover:text-purple-500 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Web search"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </button>

                  {/* Code interpreter */}
                  <button
                    type="button"
                    className="p-2 text-gray-500 hover:text-purple-500 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Code interpreter"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  )
} 