package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strconv"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/xanzy/go-gitlab"
)

var (
	APIBase        = os.Getenv("GITLAB_API_BASE")
	APIToken       = os.Getenv("GITLAB_API_TOKEN")
	WebhookToken   = os.Getenv("GITLAB_WEBHOOK_TOKEN")
	Registrator    = os.Getenv("REGISTRATOR_ID")
	AutomaticMerge = os.Getenv("AUTOMATIC_MERGE") == "true"

	// TODO: This does not  work with nested groups.
	RepoRegex    = regexp.MustCompile(`Repository:.*/(.*/.*)`)
	VersionRegex = regexp.MustCompile(`Version:\s*(v.*)`)
	CommitRegex  = regexp.MustCompile(`Commit:\s*(.*)`)

	Client *gitlab.Client
)

// Request is what we get from AWS Lambda.
type Request struct {
	Headers map[string]string `json:"headers"`
	Body    string            `json:"body"`
}

// Reponse is what we return from the handler.
type Response events.APIGatewayProxyResponse

// MergeRequestEvent contains the merge request event data.
type MergeRequestEvent struct {
	EventType string `json:"event_type"`
	Attrs     struct {
		Action       string `json:"action"`
		Author       int    `json:"author_id"`
		Description  string `json:"description"`
		Project      int    `json:"source_project_id"`
		TargetBranch string `json:"target_branch"`
		Target       struct {
			DefaultBranch string `json:"default_branch"`
		} `json:"target"`
	} `json:"object_attributes"`
	Changes struct {
		ID struct {
			Previous *int `json:"previous"`
			Current  int  `json:"current"`
		} `json:"iid"`
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
	lambda.Start(func(req Request) (resp Response, nilErr error) {
		resp = Response{StatusCode: 200}
		defer func(r *Response) {
			fmt.Println(r.Body)
		}(&resp)

		if req.Headers["X-Gitlab-Token"] != WebhookToken {
			resp.Body = "Invalid webhook token"
			return
		}

		me := MergeRequestEvent{}
		if err := json.Unmarshal([]byte(req.Body), &me); err != nil {
			resp.Body = "Parsing body: " + err.Error()
			return
		}

		var err error
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

// Handle handles the event.
func (me MergeRequestEvent) Handle() error {
	if strconv.Itoa(me.Attrs.Author) != Registrator {
		return errors.New("MR not created by Registrator")
	}
	switch a := me.Attrs.Action; a {
	case "open":
		return me.HandleOpen()
	case "merge":
		return me.HandleMerge()
	default:
		return fmt.Errorf("Unknown action (%s)", a)
	}
}

// HandleOpen handles open events.
func (me MergeRequestEvent) HandleOpen() error {
	if !AutomaticMerge {
		return errors.New("Automatic merging is disabled")
	} else if me.Changes.ID.Previous != nil {
		return errors.New("Not a new MR")
	}

	project := me.Attrs.Project
	mr := me.Changes.ID.Current

	if _, _, err := Client.MergeRequestApprovals.ApproveMergeRequest(project, mr, nil); err != nil {
		return fmt.Errorf("Approve merge request: %v", err)
	}

	opts := gitlab.AcceptMergeRequestOptions{MergeWhenPipelineSucceeds: gitlab.Bool(true)}
	if _, _, err := Client.MergeRequests.AcceptMergeRequest(project, mr, &opts); err != nil {
		return fmt.Errorf("Accept merge request: %v", err)
	}

	return nil
}

// HandleMerge handles merge events.
func (me MergeRequestEvent) HandleMerge() error {
	if me.Changes.State.Previous == "merged" {
		return errors.New("MR state was previously merged")
	} else if current := me.Changes.State.Current; current != "merged" {
		return fmt.Errorf("MR state is not merged (%s)", current)
	}

	if t := me.Attrs.TargetBranch; t != me.Attrs.Target.DefaultBranch {
		return fmt.Errorf("Invalid target branch (%s)", t)
	}

	body := me.Attrs.Description
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
	opts := gitlab.CreateTagOptions{
		TagName: gitlab.String(version),
		Ref:     gitlab.String(commit),
	}
	if _, _, err := Client.Tags.CreateTag(project, &opts); err != nil {
		return fmt.Errorf("Create tag: %v", err)
	}

	return nil
}
