'use client';

import React, { useState, useRef, useEffect } from 'react';
import { WizardStep } from '../Wizard';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface FirstChatStepProps {
    twinName: string;
    onSendMessage?: (message: string) => Promise<string>;
}

export function FirstChatStep({ twinName, onSendMessage }: FirstChatStepProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: `Hi there! 👋 I'm ${twinName}, your digital twin. I've learned from your content and I'm ready to help. Try asking me something!`
        }
    ]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const suggestedQuestions = [
        "What do you know about me?",
        "What's your expertise in?",
        "How can you help my audience?"
    ];

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async (messageText: string = input) => {
        if (!messageText.trim()) return;

        const userMessage: Message = { role: 'user', content: messageText };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsTyping(true);

        try {
            // Simulated response or real API call
            const response = onSendMessage
                ? await onSendMessage(messageText)
                : await simulateResponse(messageText, twinName);

            setMessages(prev => [...prev, { role: 'assistant', content: response }]);
        } catch (error) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "I'm still learning! Once you add more content, I'll be able to give better answers."
            }]);
        } finally {
            setIsTyping(false);
        }
    };

    const handleSuggestedClick = (question: string) => {
        handleSend(question);
    };

    return (
        <WizardStep
            title="Chat with Your Twin"
            description="Test out your new digital twin"
        >
            <div className="max-w-2xl mx-auto">
                {/* Chat Container */}
                <div className="bg-slate-900/50 border border-white/10 rounded-2xl overflow-hidden">
                    {/* Messages */}
                    <div className="h-[400px] overflow-y-auto p-4 space-y-4 scrollbar-thin">
                        {messages.map((message, index) => (
                            <div
                                key={index}
                                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div className={`flex items-start gap-3 max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                    {/* Avatar */}
                                    <div className={`
                    w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
                    ${message.role === 'user'
                                            ? 'bg-indigo-500'
                                            : 'bg-gradient-to-br from-purple-500 to-indigo-600'}
                  `}>
                                        {message.role === 'user' ? (
                                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            </svg>
                                        ) : (
                                            <span className="text-white text-xs font-bold">{twinName.charAt(0)}</span>
                                        )}
                                    </div>

                                    {/* Message Bubble */}
                                    <div className={`
                    px-4 py-3 rounded-2xl
                    ${message.role === 'user'
                                            ? 'bg-indigo-500 text-white rounded-br-sm'
                                            : 'bg-white/10 text-white rounded-bl-sm'}
                  `}>
                                        {message.content}
                                    </div>
                                </div>
                            </div>
                        ))}

                        {/* Typing Indicator */}
                        {isTyping && (
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
                                    <span className="text-white text-xs font-bold">{twinName.charAt(0)}</span>
                                </div>
                                <div className="px-4 py-3 bg-white/10 rounded-2xl rounded-bl-sm">
                                    <div className="flex gap-1">
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggested Questions */}
                    {messages.length <= 2 && (
                        <div className="px-4 py-3 border-t border-white/10">
                            <div className="text-xs text-slate-500 mb-2">Try asking:</div>
                            <div className="flex flex-wrap gap-2">
                                {suggestedQuestions.map((question, index) => (
                                    <button
                                        key={index}
                                        onClick={() => handleSuggestedClick(question)}
                                        className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm text-slate-300 transition-colors"
                                    >
                                        {question}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Input */}
                    <div className="p-4 border-t border-white/10">
                        <form
                            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                            className="flex gap-3"
                        >
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Ask your twin something..."
                                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || isTyping}
                                className="px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                            </button>
                        </form>
                    </div>
                </div>

                {/* Success Note */}
                <div className="text-center mt-6">
                    <p className="text-slate-400 text-sm">
                        🎉 Your twin is live! Click "Get Started" to go to your dashboard.
                    </p>
                </div>
            </div>
        </WizardStep>
    );
}

// Simulated response for demo purposes
async function simulateResponse(question: string, twinName: string): Promise<string> {
    await new Promise(resolve => setTimeout(resolve, 1500));

    const responses: Record<string, string> = {
        'what do you know about me': `Based on the content you've shared, I know about your expertise and can help answer questions on your behalf. As you add more content, my knowledge will grow!`,
        "what's your expertise in": `I'm trained on the content you've provided. My expertise reflects yours - whatever topics and knowledge you've shared with me.`,
        'how can you help my audience': `I can answer questions 24/7, provide consistent responses, and help scale your knowledge. Your audience can interact with me anytime, even when you're busy.`,
    };

    const lowerQuestion = question.toLowerCase();
    for (const [key, response] of Object.entries(responses)) {
        if (lowerQuestion.includes(key)) {
            return response;
        }
    }

    return `That's a great question! Based on what I've learned, I'd say this relates to your core expertise. As you add more content, I'll be able to give more specific answers.`;
}

export default FirstChatStep;
