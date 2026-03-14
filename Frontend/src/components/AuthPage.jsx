import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { AlertCircle, Building, User, Zap } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export default function AuthPage({ dispatch }) {
  const [role, setRole] = useState('employer');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [skills, setSkills] = useState('');
  const [bio, setBio] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e, mode) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let data;
      if (mode === 'login') {
        data = await api.login({ email, password });
      } else {
        const skillsList = skills.split(',').map(s => s.trim()).filter(Boolean);
        data = await api.register({
          email, password, name, role,
          skills: role === 'freelancer' ? skillsList : undefined,
          bio: role === 'freelancer' ? bio : undefined,
        });
      }
      dispatch({ type: ACTIONS.SET_TOKEN, payload: data.access_token });
      dispatch({ type: ACTIONS.SET_USER, payload: data.user });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-background p-4 relative overflow-hidden">
      {/* Dynamic Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-[100px]" />
      </div>

      <div className="z-10 flex flex-col items-center mb-8 gap-3">
        <div className="flex items-center gap-3">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <Zap className="text-white h-7 w-7" />
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight">Snack Overflow</h1>
        </div>
        <p className="text-muted-foreground font-medium text-sm sm:text-base tracking-wide uppercase">
          Autonomous AI Project & Payment Intermediary
        </p>
      </div>

      <Card className="w-full max-w-md z-10 border-border/40 shadow-2xl backdrop-blur-xl bg-card/95">
        <Tabs defaultValue="login" className="w-full">
          <CardHeader className="pb-3 border-b border-border/10 mb-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Sign In</TabsTrigger>
              <TabsTrigger value="register">Create Account</TabsTrigger>
            </TabsList>
            {error && (
              <Alert variant="destructive" className="mt-4">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardHeader>
          
          <TabsContent value="login">
            <form onSubmit={(e) => handleSubmit(e, 'login')}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Email</label>
                  <Input type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Password</label>
                  <Input type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
              </CardContent>
              <CardFooter>
                <Button type="submit" className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg transition-all" size="lg" disabled={loading}>
                  {loading ? 'Authenticating...' : 'Sign In'}
                </Button>
              </CardFooter>
            </form>
          </TabsContent>

          <TabsContent value="register">
            <form onSubmit={(e) => handleSubmit(e, 'register')}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Full Name</label>
                  <Input type="text" placeholder="Jane Doe" value={name} onChange={e => setName(e.target.value)} required />
                </div>
                
                <div className="space-y-3">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">I am a...</label>
                  <div className="grid grid-cols-2 gap-4">
                    <div 
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 cursor-pointer transition-all ${role === 'employer' ? 'border-cyan-500 bg-cyan-500/10' : 'border-border bg-background hover:bg-muted/50'}`}
                      onClick={() => setRole('employer')}
                    >
                      <Building className={`h-8 w-8 mb-2 ${role === 'employer' ? 'text-cyan-500' : 'text-muted-foreground'}`} />
                      <span className="font-semibold text-sm">Employer</span>
                    </div>
                    <div 
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 cursor-pointer transition-all ${role === 'freelancer' ? 'border-blue-500 bg-blue-500/10' : 'border-border bg-background hover:bg-muted/50'}`}
                      onClick={() => setRole('freelancer')}
                    >
                      <User className={`h-8 w-8 mb-2 ${role === 'freelancer' ? 'text-blue-500' : 'text-muted-foreground'}`} />
                      <span className="font-semibold text-sm">Freelancer</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Email</label>
                  <Input type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Password</label>
                  <Input type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
                </div>

                {role === 'freelancer' && (
                  <>
                    <div className="space-y-2">
                      <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Skills (comma-separated)</label>
                      <Input type="text" placeholder="React, Python, UI/UX" value={skills} onChange={e => setSkills(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Short Bio</label>
                      <textarea
                        className="w-full min-h-[90px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        placeholder="Tell employers about your expertise and recent work..."
                        value={bio}
                        onChange={e => setBio(e.target.value)}
                      />
                    </div>
                  </>
                )}
              </CardContent>
              <CardFooter>
                <Button type="submit" className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg transition-all" size="lg" disabled={loading}>
                  {loading ? 'Creating Account...' : 'Create Account'}
                </Button>
              </CardFooter>
            </form>
          </TabsContent>
        </Tabs>
      </Card>
      
      <p className="mt-8 text-sm text-muted-foreground z-10">
        Secured by Decentralized Escrow Ledger
      </p>
    </div>
  );
}
