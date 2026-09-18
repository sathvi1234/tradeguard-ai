#!/usr/bin/env python3
"""
TradeGuard AI Test Runner Script
Comprehensive test execution for backend and frontend.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class TestRunner:
    """Comprehensive test runner for TradeGuard AI."""
    
    def __init__(self):
        self.root_path = Path(__file__).parent.parent
        self.backend_path = self.root_path / "backend"
        self.frontend_path = self.root_path / "frontend"
        self.results: Dict[str, Dict] = {}
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}{Colors.END}")
    
    def print_success(self, message: str):
        """Print a success message."""
        print(f"{Colors.GREEN}✓ {message}{Colors.END}")
    
    def print_error(self, message: str):
        """Print an error message."""
        print(f"{Colors.RED}✗ {message}{Colors.END}")
    
    def print_warning(self, message: str):
        """Print a warning message."""
        print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")
    
    def print_info(self, message: str):
        """Print an info message."""
        print(f"{Colors.BLUE}ℹ {message}{Colors.END}")
    
    def run_backend_tests(self, test_type: str = "all", verbose: bool = False) -> bool:
        """Run backend tests with pytest."""
        self.print_header("Running Backend Tests")
        
        if not self.backend_path.exists():
            self.print_error("Backend directory not found")
            return False
        
        # Change to backend directory
        os.chdir(self.backend_path)
        
        # Build pytest command
        cmd = ["python", "-m", "pytest"]
        
        if test_type == "unit":
            cmd.extend(["-m", "unit"])
        elif test_type == "integration":
            cmd.extend(["-m", "integration"])
        elif test_type == "security":
            cmd.extend(["-m", "security"])
        elif test_type != "all":
            cmd.extend(["-k", test_type])
        
        if verbose:
            cmd.extend(["-v", "-s"])
        else:
            cmd.append("-q")
        
        # Add coverage for full test runs
        if test_type == "all":
            cmd.extend(["--cov=app", "--cov-report=term-missing"])
        
        self.print_info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            self.results["backend"] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.print_success("Backend tests passed")
                if verbose:
                    print(result.stdout)
                return True
            else:
                self.print_error("Backend tests failed")
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.print_error("Backend tests timed out")
            return False
        except Exception as e:
            self.print_error(f"Error running backend tests: {e}")
            return False
    
    def run_frontend_tests(self, test_type: str = "all", verbose: bool = False) -> bool:
        """Run frontend tests with Jest."""
        self.print_header("Running Frontend Tests")
        
        if not self.frontend_path.exists():
            self.print_error("Frontend directory not found")
            return False
        
        # Change to frontend directory
        os.chdir(self.frontend_path)
        
        # Check if node_modules exists
        if not (self.frontend_path / "node_modules").exists():
            self.print_error("node_modules not found. Run 'npm install' first.")
            return False
        
        # Build Jest command
        cmd = ["npm", "run"]
        
        if test_type == "all":
            cmd.append("test:ci")
        elif test_type == "coverage":
            cmd.append("test:coverage")
        else:
            cmd.extend(["test", "--", "--testNamePattern", test_type])
        
        if verbose and test_type not in ["all", "coverage"]:
            cmd.extend(["--", "--verbose"])
        
        self.print_info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            self.results["frontend"] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.print_success("Frontend tests passed")
                if verbose:
                    print(result.stdout)
                return True
            else:
                self.print_error("Frontend tests failed")
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.print_error("Frontend tests timed out")
            return False
        except Exception as e:
            self.print_error(f"Error running frontend tests: {e}")
            return False
    
    def run_linting(self) -> bool:
        """Run linting for both backend and frontend."""
        self.print_header("Running Code Quality Checks")
        
        success = True
        
        # Backend linting
        self.print_info("Checking backend code quality...")
        os.chdir(self.backend_path)
        
        # Run flake8 if available
        try:
            result = subprocess.run(
                ["python", "-m", "flake8", "app", "tests"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.print_success("Backend linting passed")
            else:
                self.print_error("Backend linting failed")
                print(result.stdout)
                success = False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.print_warning("Backend linting skipped (flake8 not available)")
        
        # Frontend linting
        self.print_info("Checking frontend code quality...")
        os.chdir(self.frontend_path)
        
        try:
            result = subprocess.run(
                ["npm", "run", "lint"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.print_success("Frontend linting passed")
            else:
                self.print_error("Frontend linting failed")
                print(result.stdout)
                success = False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.print_warning("Frontend linting skipped")
        
        # TypeScript checking
        self.print_info("Checking TypeScript types...")
        
        try:
            result = subprocess.run(
                ["npm", "run", "type-check"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.print_success("TypeScript checking passed")
            else:
                self.print_error("TypeScript checking failed")
                print(result.stdout)
                success = False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.print_warning("TypeScript checking skipped")
        
        return success
    
    def run_security_tests(self, verbose: bool = False) -> bool:
        """Run security-focused tests."""
        self.print_header("Running Security Tests")
        
        success = True
        
        # Backend security tests
        os.chdir(self.backend_path)
        backend_security = self.run_backend_tests("security", verbose)
        if not backend_security:
            success = False
        
        # Run security checker script
        security_script = self.root_path / "scripts" / "security_check.py"
        if security_script.exists():
            self.print_info("Running security validation script...")
            
            try:
                result = subprocess.run(
                    ["python", str(security_script)],
                    cwd=self.root_path,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    self.print_success("Security validation passed")
                else:
                    self.print_error("Security validation failed")
                    if verbose:
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    success = False
                    
            except Exception as e:
                self.print_error(f"Security validation error: {e}")
                success = False
        
        return success
    
    def generate_test_report(self) -> None:
        """Generate a comprehensive test report."""
        self.print_header("Test Report")
        
        total_tests = 0
        passed_tests = 0
        
        for component, result in self.results.items():
            if result["returncode"] == 0:
                self.print_success(f"{component.title()} tests: PASSED")
                passed_tests += 1
            else:
                self.print_error(f"{component.title()} tests: FAILED")
            total_tests += 1
        
        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Total test suites: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {total_tests - passed_tests}")
        
        if passed_tests == total_tests:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.END}")
        
        # Save detailed report
        report_file = self.root_path / "test_report.txt"
        with open(report_file, 'w') as f:
            f.write("TradeGuard AI Test Report\n")
            f.write("=" * 50 + "\n\n")
            
            for component, result in self.results.items():
                f.write(f"{component.upper()} TESTS\n")
                f.write("-" * 20 + "\n")
                f.write(f"Return code: {result['returncode']}\n")
                f.write(f"Output:\n{result['stdout']}\n")
                if result['stderr']:
                    f.write(f"Errors:\n{result['stderr']}\n")
                f.write("\n")
        
        print(f"\nDetailed report saved to: {report_file}")
    
    def run_all_tests(self, verbose: bool = False) -> bool:
        """Run all tests."""
        self.print_header("Running Complete Test Suite")
        
        all_passed = True
        
        # Check dependencies first
        if not self.check_dependencies():
            self.print_error("Dependency check failed")
            return False
        
        # Run linting
        if not self.run_linting():
            self.print_warning("Code quality checks failed")
            all_passed = False
        
        # Run backend tests
        if not self.run_backend_tests("all", verbose):
            all_passed = False
        
        # Run frontend tests
        if not self.run_frontend_tests("all", verbose):
            all_passed = False
        
        # Run security tests
        if not self.run_security_tests(verbose):
            all_passed = False
        
        # Generate report
        self.generate_test_report()
        
        return all_passed
    
    def check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        self.print_info("Checking test dependencies...")
        
        success = True
        
        # Check Python and pytest
        try:
            subprocess.run(["python", "--version"], check=True, capture_output=True)
            subprocess.run(["python", "-m", "pytest", "--version"], check=True, capture_output=True)
            self.print_success("Python and pytest available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.print_error("Python or pytest not available")
            success = False
        
        # Check Node.js and npm
        try:
            subprocess.run(["node", "--version"], check=True, capture_output=True)
            subprocess.run(["npm", "--version"], check=True, capture_output=True)
            self.print_success("Node.js and npm available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.print_error("Node.js or npm not available")
            success = False
        
        return success


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="TradeGuard AI Test Runner")
    
    parser.add_argument(
        "--component",
        choices=["backend", "frontend", "all"],
        default="all",
        help="Component to test"
    )
    
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "security", "all"],
        default="all",
        help="Type of tests to run"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="Run only linting and code quality checks"
    )
    
    parser.add_argument(
        "--security-only",
        action="store_true",
        help="Run only security tests"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    success = False
    
    try:
        if args.lint_only:
            success = runner.run_linting()
        elif args.security_only:
            success = runner.run_security_tests(args.verbose)
        elif args.component == "backend":
            success = runner.run_backend_tests(args.type, args.verbose)
        elif args.component == "frontend":
            success = runner.run_frontend_tests(args.type, args.verbose)
        else:
            success = runner.run_all_tests(args.verbose)
        
        if success:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Tests completed successfully{Colors.END}")
            sys.exit(0)
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Tests failed{Colors.END}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test execution interrupted{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Test execution error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()