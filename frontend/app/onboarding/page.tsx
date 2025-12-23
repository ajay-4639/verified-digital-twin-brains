'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import {
    Wizard,
    WelcomeStep,
    ClaimIdentityStep,
    DefineExpertiseStep,
    AddContentStep,
    SeedFAQsStep,
    SetPersonalityStep,
    PreviewTwinStep,
    LaunchStep
} from '@/components/onboarding';

// 8-Step Delphi-Style Onboarding
const WIZARD_STEPS = [
    { id: 'welcome', title: 'Welcome', description: 'Get started', icon: '👋' },
    { id: 'identity', title: 'Identity', description: 'Claim your name', icon: '✨' },
    { id: 'expertise', title: 'Expertise', description: 'Define domains', icon: '🎯' },
    { id: 'content', title: 'Content', description: 'Add knowledge', icon: '📚' },
    { id: 'faqs', title: 'FAQs', description: 'Seed answers', icon: '❓' },
    { id: 'personality', title: 'Personality', description: 'Set tone', icon: '🎭' },
    { id: 'preview', title: 'Preview', description: 'Test twin', icon: '👁️' },
    { id: 'launch', title: 'Launch', description: 'Go live', icon: '🚀' },
];

interface PersonalitySettings {
    tone: 'professional' | 'friendly' | 'casual' | 'technical';
    responseLength: 'concise' | 'balanced' | 'detailed';
    firstPerson: boolean;
    customInstructions: string;
}

interface FAQPair {
    question: string;
    answer: string;
}

export default function OnboardingPage() {
    const router = useRouter();
    const supabase = getSupabaseClient();

    // State
    const [currentStep, setCurrentStep] = useState(0);
    const [twinId, setTwinId] = useState<string | null>(null);

    // Step 2: Identity
    const [twinName, setTwinName] = useState('');
    const [handle, setHandle] = useState('');
    const [tagline, setTagline] = useState('');

    // Step 3: Expertise
    const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
    const [customExpertise, setCustomExpertise] = useState<string[]>([]);

    // Step 4: Content
    const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
    const [pendingUrls, setPendingUrls] = useState<string[]>([]);

    // Step 5: FAQs
    const [faqs, setFaqs] = useState<FAQPair[]>([]);

    // Step 6: Personality
    const [personality, setPersonality] = useState<PersonalitySettings>({
        tone: 'friendly',
        responseLength: 'balanced',
        firstPerson: true,
        customInstructions: ''
    });

    // Check if should skip onboarding (returning user with existing twins)
    useEffect(() => {
        const checkExistingTwins = async () => {
            const { data: twins } = await supabase
                .from('twins')
                .select('id')
                .limit(1);

            if (twins && twins.length > 0) {
                router.push('/dashboard');
            }
        };
        checkExistingTwins();
    }, []);

    const handleFileUpload = (files: File[]) => {
        setUploadedFiles(prev => [...prev, ...files]);
    };

    const handleUrlSubmit = (url: string) => {
        setPendingUrls(prev => [...prev, url]);
    };

    const handleStepChange = async (newStep: number) => {
        // Create twin after identity step
        if (currentStep === 1 && newStep === 2 && twinName && !twinId) {
            await createTwin();
        }

        // Upload content after content step
        if (currentStep === 3 && newStep === 4 && twinId) {
            await uploadContent();
        }

        // Save FAQs after FAQ step
        if (currentStep === 4 && newStep === 5 && twinId) {
            await saveFaqs();
        }

        // Save personality after personality step
        if (currentStep === 5 && newStep === 6 && twinId) {
            await savePersonality();
        }

        setCurrentStep(newStep);
    };

    const createTwin = async () => {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) return;

            const expertiseText = [...selectedDomains, ...customExpertise].join(', ');

            const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

            const { data, error } = await supabase
                .from('twins')
                .insert({
                    name: twinName,
                    tenant_id: user.id,
                    owner_id: user.id,
                    system_instructions: systemInstructions,
                    specialization_id: 'vanilla',
                    settings: {
                        handle,
                        tagline,
                        expertise: [...selectedDomains, ...customExpertise],
                        personality
                    }
                })
                .select()
                .single();

            if (!error && data) {
                setTwinId(data.id);
            }
        } catch (error) {
            console.error('Error creating twin:', error);
        }
    };

    const uploadContent = async () => {
        if (!twinId) return;

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

        // Upload files
        for (const file of uploadedFiles) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('twin_id', twinId);

            try {
                await fetch(`${backendUrl}/ingest/document`, {
                    method: 'POST',
                    body: formData,
                });
            } catch (error) {
                console.error('Error uploading file:', error);
            }
        }

        // Submit URLs
        for (const url of pendingUrls) {
            try {
                await fetch(`${backendUrl}/ingest/url`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, twin_id: twinId }),
                });
            } catch (error) {
                console.error('Error submitting URL:', error);
            }
        }
    };

    const saveFaqs = async () => {
        if (!twinId) return;

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const { data: { user } } = await supabase.auth.getUser();

        for (const faq of faqs) {
            if (faq.question && faq.answer) {
                try {
                    await fetch(`${backendUrl}/twins/${twinId}/verified-qna`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            question: faq.question,
                            answer: faq.answer,
                            owner_id: user?.id
                        }),
                    });
                } catch (error) {
                    console.error('Error saving FAQ:', error);
                }
            }
        }
    };

    const savePersonality = async () => {
        if (!twinId) return;

        const expertiseText = [...selectedDomains, ...customExpertise].join(', ');

        const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

        try {
            await supabase
                .from('twins')
                .update({
                    system_instructions: systemInstructions,
                    settings: {
                        handle,
                        tagline,
                        expertise: [...selectedDomains, ...customExpertise],
                        personality
                    }
                })
                .eq('id', twinId);
        } catch (error) {
            console.error('Error saving personality:', error);
        }
    };

    const handleLaunch = async () => {
        if (!twinId) return;

        // Mark twin as active
        await supabase
            .from('twins')
            .update({ is_active: true })
            .eq('id', twinId);

        // Save onboarding completed flag
        localStorage.setItem('onboardingCompleted', 'true');
    };

    const handleComplete = () => {
        if (twinId) {
            router.push(`/dashboard`);
        } else {
            router.push('/dashboard');
        }
    };

    const renderStep = () => {
        switch (currentStep) {
            case 0:
                return <WelcomeStep />;
            case 1:
                return (
                    <ClaimIdentityStep
                        twinName={twinName}
                        handle={handle}
                        tagline={tagline}
                        onTwinNameChange={setTwinName}
                        onHandleChange={setHandle}
                        onTaglineChange={setTagline}
                    />
                );
            case 2:
                return (
                    <DefineExpertiseStep
                        selectedDomains={selectedDomains}
                        customExpertise={customExpertise}
                        onDomainsChange={setSelectedDomains}
                        onCustomExpertiseChange={setCustomExpertise}
                    />
                );
            case 3:
                return (
                    <AddContentStep
                        onFileUpload={handleFileUpload}
                        onUrlSubmit={handleUrlSubmit}
                        uploadedFiles={uploadedFiles}
                        pendingUrls={pendingUrls}
                    />
                );
            case 4:
                return (
                    <SeedFAQsStep
                        faqs={faqs}
                        onFaqsChange={setFaqs}
                        expertiseDomains={selectedDomains}
                    />
                );
            case 5:
                return (
                    <SetPersonalityStep
                        personality={personality}
                        onPersonalityChange={setPersonality}
                        twinName={twinName || 'Your Twin'}
                    />
                );
            case 6:
                return (
                    <PreviewTwinStep
                        twinId={twinId}
                        twinName={twinName || 'Your Twin'}
                        tagline={tagline}
                    />
                );
            case 7:
                return (
                    <LaunchStep
                        twinName={twinName || 'Your Twin'}
                        handle={handle}
                        twinId={twinId}
                        onLaunch={handleLaunch}
                    />
                );
            default:
                return null;
        }
    };

    return (
        <Wizard
            steps={WIZARD_STEPS}
            currentStep={currentStep}
            onStepChange={handleStepChange}
            onComplete={handleComplete}
            allowSkip={currentStep === 3 || currentStep === 4} // Allow skip on content and FAQ steps
        >
            {renderStep()}
        </Wizard>
    );
}
