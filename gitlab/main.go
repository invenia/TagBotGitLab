package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"regexp"
	"strings"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/xanzy/go-gitlab"
)

var (
	APIBase      = os.Getenv("GITLAB_API_BASE")
	APIToken     = os.Getenv("GITLAB_API_TOKEN")
	WebhookToken = os.Getenv("GITLAB_WEBHOOK_TOKEN")

	// TODO: This does not  work with nested groups.
	RepoRegex    = regexp.MustCompile(`Repository:.*/(.*/.*)`)
	VersionRegex = regexp.MustCompile(`Version:\s*(v.*)`)
	CommitRegex  = regexp.MustCompile(`Commit:\s*(.*)`)

	Client *gitlab.Client
)

// LambdaRequest is what we get from AWS Lambda.
type LambdaRequest struct {
	Method  string            `json:"httpMethod"`
	Headers map[string]string `json:"headers"`
	Body    string            `json:"body"`
}

// Reponse is what we return from the handler.
type Response events.APIGatewayProxyResponse

// MergeEvent contains the merge request event data.
type MergeEvent struct {
	EventType        string `json:"event_type"`
	ObjectAttributes struct {
		Action       string `json:"action"`
		Description  string `json:"description"`
		TargetBranch string `json:"target_branch"`
		Target       struct {
			DefaultBranch string `json:"default_branch"`
		}
	} `json:"object_attributes"`
	Changes struct {
		State struct {
			Previous string `json:"previous"`
			Current  string `json:"current"`
		} `json:"state"`
	} `json:"changes"`
}

func init() {
	Client = gitlab.NewClient(nil, APIToken)
	Client.SetBaseURL(APIBase)
}

func main() {
	lambda.Start(func(lr LambdaRequest) (resp Response, nilErr error) {
		resp = Response{StatusCode: 200}
		defer func(r *Response) {
			fmt.Println(r.Body)
		}(&resp)

		req, err := LambdaToHttp(lr)
		if err != nil {
			resp.Body = "Converting request: " + err.Error()
			return
		}

		if req.Header.Get("X-GitLab-Token") != WebhookToken {
			resp.Body = "Invalid webhook token"
			return
		}

		payload, err := ioutil.ReadAll(req.Body)
		if err != nil {
			resp.Body = "Reading body: " + err.Error()
			return
		}

		me := &MergeEvent{}
		if err = json.Unmarshal(payload, me); err != nil {
			resp.Body = "Parsing body: " + err.Error()
			return
		}

		if me.EventType == "merge_request" {
			err = me.Handle()
		} else {
			err = fmt.Errorf("Unknown event type (%s)", me.EventType)
		}

		if err == nil {
			resp.Body = "No error"
		} else {
			resp.Body = err.Error()
		}

		return
	})
}

// LambdaToHttp converts a Lambda request to an HTTP request.
func LambdaToHttp(lr LambdaRequest) (*http.Request, error) {
	r, err := http.NewRequest(lr.Method, "", strings.NewReader(lr.Body))
	if err != nil {
		return nil, err
	}
	for k, v := range lr.Headers {
		r.Header.Add(k, v)
	}
	return r, nil
}

// Handle handles the event.
func (me MergeEvent) Handle() error {
	if action := me.ObjectAttributes.Action; action != "merge" {
		return fmt.Errorf("Not a merge event (%s)", action)
	} else if me.Changes.State.Previous == "merged" {
		return errors.New("MR state was previously merged")
	} else if current := me.Changes.State.Current; current != "merged" {
		return fmt.Errorf("MR state is not merged (%s)", current)
	}

	if target := me.ObjectAttributes.TargetBranch; target != me.ObjectAttributes.Target.DefaultBranch {
		return fmt.Errorf("Invalid target branch (%s)", target)
	}

	body := me.ObjectAttributes.Description
	fmt.Println("MR body:\n" + body)

	match := RepoRegex.FindStringSubmatch(body)
	if match == nil {
		return errors.New("No repo match")
	}
	project := match[1]

	match = VersionRegex.FindStringSubmatch(body)
	if match == nil {
		return errors.New("No version match")
	}
	version := match[1]

	match = CommitRegex.FindStringSubmatch(body)
	if match == nil {
		return errors.New("No commit match")
	}
	commit := match[1]

	fmt.Printf("Creating tag %s for %s at %s\n", version, project, commit)

	opts := &gitlab.CreateTagOptions{
		TagName: gitlab.String(version),
		Ref:     gitlab.String(commit),
	}
	if _, _, err := Client.Tags.CreateTag(project, opts); err != nil {
		return fmt.Errorf("Create tag: %v", err)
	}

	return nil
}
