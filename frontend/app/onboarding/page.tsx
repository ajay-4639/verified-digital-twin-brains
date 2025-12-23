'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import {
    Wizard,
    WelcomeStep,
    CreateTwinStep,
    AddContentStep,
    TrainingStep,
    FirstChatStep
} from '@/components/onboarding';

const WIZARD_STEPS = [
    { id: 'welcome', title: 'Welcome', description: 'Get started', icon: '👋' },
    { id: 'create', title: 'Create', description: 'Name your twin', icon: '✏️' },
    { id: 'content', title: 'Content', description: 'Add knowledge', icon: '📚' },
    { id: 'training', title: 'Training', description: 'Build your twin', icon: '🧠' },
    { id: 'chat', title: 'Chat', description: 'Test it out', icon: '💬' },
];

export default function OnboardingPage() {
    const router = useRouter();
    const supabase = getSupabaseClient();

    const [currentStep, setCurrentStep] = useState(0);
    const [twinName, setTwinName] = useState('');
    const [twinPurpose, setTwinPurpose] = useState('');
    const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
    const [pendingUrls, setPendingUrls] = useState<string[]>([]);
    const [isTraining, setIsTraining] = useState(false);
    const [trainingProgress, setTrainingProgress] = useState(0);
    const [twinId, setTwinId] = useState<string | null>(null);

    // Check if should skip onboarding (returning user with existing twins)
    useEffect(() => {
        const checkExistingTwins = async () => {
            const { data: twins } = await supabase
                .from('twins')
                .select('id')
                .limit(1);

            if (twins && twins.length > 0) {
                // User already has twins, redirect to dashboard
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
        // Handle special step transitions
        if (currentStep === 1 && newStep === 2 && twinName) {
            // Create twin when leaving create step
            await createTwin();
        }

        if (currentStep === 2 && newStep === 3) {
            // Start training when leaving content step
            await uploadContent();
            setIsTraining(true);
        }

        setCurrentStep(newStep);
    };

    const createTwin = async () => {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) return;

            const { data, error } = await supabase
                .from('twins')
                .insert({
                    name: twinName,
                    tenant_id: user.id,
                    owner_id: user.id,
                    system_instructions: `You are ${twinName}, a digital twin with expertise in ${twinPurpose || 'general topics'}.`,
                    specialization_id: 'vanilla'
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

    const handleComplete = () => {
        // Save onboarding completed flag
        localStorage.setItem('onboardingCompleted', 'true');

        // Navigate to dashboard
        if (twinId) {
            router.push(`/dashboard/twins/${twinId}?tab=overview`);
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
                    <CreateTwinStep
                        twinName={twinName}
                        twinPurpose={twinPurpose}
                        onTwinNameChange={setTwinName}
                        onTwinPurposeChange={setTwinPurpose}
                    />
                );
            case 2:
                return (
                    <AddContentStep
                        onFileUpload={handleFileUpload}
                        onUrlSubmit={handleUrlSubmit}
                        uploadedFiles={uploadedFiles}
                        pendingUrls={pendingUrls}
                    />
                );
            case 3:
                return (
                    <TrainingStep
                        twinName={twinName || 'Your Twin'}
                        contentCount={uploadedFiles.length + pendingUrls.length}
                        isTraining={isTraining}
                        trainingProgress={trainingProgress}
                    />
                );
            case 4:
                return (
                    <FirstChatStep
                        twinName={twinName || 'Your Twin'}
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
            allowSkip={currentStep === 2} // Only allow skip on content step
        >
            {renderStep()}
        </Wizard>
    );
}
