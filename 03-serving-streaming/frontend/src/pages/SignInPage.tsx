import { SignIn } from '@clerk/clerk-react'

export function SignInPage() {
  return (
    <div className="flex justify-center py-12">
      <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" />
    </div>
  )
}
