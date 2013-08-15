// Copyright 2013 Canonical Ltd.
// Licensed under the AGPLv3, see LICENCE file for details.

package imagemetadata

import (
	"flag"
	"reflect"
	"testing"

	"launchpad.net/goamz/aws"
	gc "launchpad.net/gocheck"

	"launchpad.net/juju-core/environs/simplestreams"
	sstesting "launchpad.net/juju-core/environs/simplestreams/testing"
)

var live = flag.Bool("live", false, "Include live simplestreams tests")
var vendor = flag.String("vendor", "", "The vendor representing the source of the simplestream data")

type liveTestData struct {
	baseURL        string
	requireSigned  bool
	validCloudSpec simplestreams.CloudSpec
}

var liveUrls = map[string]liveTestData{
	"ec2": {
		baseURL:        simplestreams.DefaultBaseURL,
		requireSigned:  true,
		validCloudSpec: simplestreams.CloudSpec{"us-east-1", aws.Regions["us-east-1"].EC2Endpoint},
	},
	"canonistack": {
		baseURL:        "https://swift.canonistack.canonical.com/v1/AUTH_a48765cc0e864be980ee21ae26aaaed4/simplestreams/data",
		requireSigned:  false,
		validCloudSpec: simplestreams.CloudSpec{"lcy01", "https://keystone.canonistack.canonical.com:443/v2.0/"},
	},
}

func Test(t *testing.T) {
	if *live {
		if *vendor == "" {
			t.Fatal("missing vendor")
		}
		var ok bool
		var testData liveTestData
		if testData, ok = liveUrls[*vendor]; !ok {
			keys := reflect.ValueOf(liveUrls).MapKeys()
			t.Fatalf("Unknown vendor %s. Must be one of %s", *vendor, keys)
		}
		registerLiveSimpleStreamsTests(testData.baseURL, NewImageConstraint(simplestreams.LookupParams{
			CloudSpec: testData.validCloudSpec,
			Series:    "quantal",
			Arches:    []string{"amd64"},
		}), testData.requireSigned)
	}
	registerSimpleStreamsTests()
	gc.TestingT(t)
}

func registerSimpleStreamsTests() {
	gc.Suite(&simplestreamsSuite{
		LocalLiveSimplestreamsSuite: sstesting.LocalLiveSimplestreamsSuite{
			BaseURL:       "test:",
			RequireSigned: false,
			ValidConstraint: NewImageConstraint(simplestreams.LookupParams{
				CloudSpec: simplestreams.CloudSpec{
					Region:   "us-east-1",
					Endpoint: "https://ec2.us-east-1.amazonaws.com",
				},
				Series: "precise",
				Arches: []string{"amd64", "arm"},
			}),
		},
	})
}

func registerLiveSimpleStreamsTests(baseURL string, validImageConstraint simplestreams.LookupConstraint, requireSigned bool) {
	gc.Suite(&sstesting.LocalLiveSimplestreamsSuite{
		BaseURL:         baseURL,
		RequireSigned:   requireSigned,
		ValidConstraint: validImageConstraint,
	})
}

type simplestreamsSuite struct {
	sstesting.LocalLiveSimplestreamsSuite
	sstesting.TestDataSuite
}

func (s *simplestreamsSuite) SetUpSuite(c *gc.C) {
	s.LocalLiveSimplestreamsSuite.SetUpSuite(c)
	s.TestDataSuite.SetUpSuite(c)
}

func (s *simplestreamsSuite) TearDownSuite(c *gc.C) {
	s.TestDataSuite.TearDownSuite(c)
	s.LocalLiveSimplestreamsSuite.TearDownSuite(c)
}

var fetchTests = []struct {
	region string
	series string
	arches []string
	images []*ImageMetadata
}{
	{
		region: "us-east-1",
		series: "precise",
		arches: []string{"amd64", "arm"},
		images: []*ImageMetadata{
			{
				Id:         "ami-442ea674",
				VType:      "hvm",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "ebs",
			},
			{
				Id:         "ami-442ea684",
				VType:      "pv",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "instance",
			},
			{
				Id:         "ami-442ea699",
				VType:      "pv",
				Arch:       "arm",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "ebs",
			},
		},
	},
	{
		region: "us-east-1",
		series: "precise",
		arches: []string{"amd64"},
		images: []*ImageMetadata{
			{
				Id:         "ami-442ea674",
				VType:      "hvm",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "ebs",
			},
			{
				Id:         "ami-442ea684",
				VType:      "pv",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "instance",
			},
		},
	},
	{
		region: "us-east-1",
		series: "precise",
		arches: []string{"arm"},
		images: []*ImageMetadata{
			{
				Id:         "ami-442ea699",
				VType:      "pv",
				Arch:       "arm",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "ebs",
			},
		},
	},
	{
		region: "us-east-1",
		series: "precise",
		arches: []string{"amd64"},
		images: []*ImageMetadata{
			{
				Id:         "ami-442ea674",
				VType:      "hvm",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "ebs",
			},
			{
				Id:         "ami-442ea684",
				VType:      "pv",
				Arch:       "amd64",
				RegionName: "us-east-1",
				Endpoint:   "https://ec2.us-east-1.amazonaws.com",
				Storage:    "instance",
			},
		},
	},
}

func (s *simplestreamsSuite) TestFetch(c *gc.C) {
	for i, t := range fetchTests {
		c.Logf("test %d", i)
		imageConstraint := NewImageConstraint(simplestreams.LookupParams{
			CloudSpec: simplestreams.CloudSpec{t.region, "https://ec2.us-east-1.amazonaws.com"},
			Series:    "precise",
			Arches:    t.arches,
		})
		images, err := Fetch([]string{s.BaseURL}, simplestreams.DefaultIndexPath, imageConstraint, s.RequireSigned)
		if !c.Check(err, gc.IsNil) {
			continue
		}
		c.Check(images, gc.DeepEquals, t.images)
	}
}

type productSpecSuite struct{}

var _ = gc.Suite(&productSpecSuite{})

func (s *productSpecSuite) TestIdWithDefaultStream(c *gc.C) {
	imageConstraint := NewImageConstraint(simplestreams.LookupParams{
		Series: "precise",
		Arches: []string{"amd64"},
	})
	ids, err := imageConstraint.Ids()
	c.Assert(err, gc.IsNil)
	c.Assert(ids, gc.DeepEquals, []string{"com.ubuntu.cloud:server:12.04:amd64"})
}

func (s *productSpecSuite) TestId(c *gc.C) {
	imageConstraint := NewImageConstraint(simplestreams.LookupParams{
		Series: "precise",
		Arches: []string{"amd64"},
		Stream: "daily",
	})
	ids, err := imageConstraint.Ids()
	c.Assert(err, gc.IsNil)
	c.Assert(ids, gc.DeepEquals, []string{"com.ubuntu.cloud.daily:server:12.04:amd64"})
}

func (s *productSpecSuite) TestIdMultiArch(c *gc.C) {
	imageConstraint := NewImageConstraint(simplestreams.LookupParams{
		Series: "precise",
		Arches: []string{"amd64", "i386"},
		Stream: "daily",
	})
	ids, err := imageConstraint.Ids()
	c.Assert(err, gc.IsNil)
	c.Assert(ids, gc.DeepEquals, []string{
		"com.ubuntu.cloud.daily:server:12.04:amd64",
		"com.ubuntu.cloud.daily:server:12.04:i386"})
}

func (s *productSpecSuite) TestIdWithNonDefaultRelease(c *gc.C) {
	imageConstraint := NewImageConstraint(simplestreams.LookupParams{
		Series: "lucid",
		Arches: []string{"amd64"},
		Stream: "daily",
	})
	ids, err := imageConstraint.Ids()
	if err != nil && err.Error() == `invalid series "lucid"` {
		c.Fatalf(`Unable to lookup series "lucid", you may need to: apt-get install distro-info`)
	}
	c.Assert(err, gc.IsNil)
	c.Assert(ids, gc.DeepEquals, []string{"com.ubuntu.cloud.daily:server:10.04:amd64"})
}
